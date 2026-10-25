"""Запуск Java в изолированных Docker-контейнерах JDK 21.

Каждый вариант исходника (original / repaired) получает один контейнер:
компиляция один раз, затем все stdin-тесты внутри него. После завершения
набора (или по TTL) контейнер принудительно удаляется.
"""

from __future__ import annotations

import contextlib
import logging
import re
import shutil
import subprocess
import tempfile
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

_CLASS_RE = re.compile(
    r"\b(?:public\s+)?(?:final\s+|abstract\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)\b"
)
_MAX_OUTPUT = 32_000
_SAFE_CLASS_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Фиксированный скрипт внутри контейнера: без подстановки пользовательского кода в shell.
_SUITE_SCRIPT = """#!/bin/bash
set -eu
CLASS="$1"
CASE_TIMEOUT="$2"
javac "${CLASS}.java" > compile.out 2> compile.err
echo $? > compile.exit
if [ "$(cat compile.exit)" != "0" ]; then
  echo COMPILE_FAIL > suite.status
  exit 0
fi
echo COMPILE_OK > suite.status
i=0
while [ -f "case_${i}.in" ]; do
  set +e
  timeout --signal=KILL "${CASE_TIMEOUT}" java -Xmx128m "${CLASS}" \
    < "case_${i}.in" > "case_${i}.out" 2> "case_${i}.err"
  echo $? > "case_${i}.exit"
  set -e
  i=$((i + 1))
done
echo DONE > suite.status
"""


@dataclass(frozen=True, slots=True)
class JavaRunResult:
    status: str  # pass | fail | error | skipped
    exit_code: int | None
    stdout: str
    stderr: str
    detail: str


@dataclass(frozen=True, slots=True)
class JavaSuiteCase:
    """Один stdin-сценарий внутри набора."""

    case_id: str
    stdin_text: str


@dataclass(frozen=True, slots=True)
class JavaSuiteCaseResult:
    case_id: str
    status: str
    exit_code: int | None
    stdout: str
    stderr: str
    detail: str


@dataclass(frozen=True, slots=True)
class JavaSuiteResult:
    """Результат одного контейнера на весь набор тестов варианта кода."""

    status: str  # ok | skipped | error | timeout
    detail: str
    container_name: str | None
    results: tuple[JavaSuiteCaseResult, ...]


def docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        completed = subprocess.run(
            ["docker", "info"],  # noqa: S607
            capture_output=True,
            timeout=8,
            check=False,
        )
        return completed.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def detect_main_class(source: str, hint: str | None = None) -> str:
    if hint and _SAFE_CLASS_RE.fullmatch(hint):
        return hint
    names = _CLASS_RE.findall(source)
    if "Main" in names:
        return "Main"
    if names:
        return names[0]
    return "Main"


def run_java_source(
    *,
    source: str,
    stdin_text: str,
    main_class: str | None = None,
    timeout_seconds: float | None = None,
    settings: Settings | None = None,
) -> JavaRunResult:
    """Компилирует и запускает один сценарий (обертка над suite из одного кейса)."""
    cfg = settings or get_settings()
    case_timeout = timeout_seconds if timeout_seconds is not None else cfg.java_case_timeout_seconds
    suite = run_java_test_suite(
        source=source,
        cases=(JavaSuiteCase(case_id="single", stdin_text=stdin_text),),
        main_class=main_class,
        variant_label="single",
        settings=cfg,
        case_timeout_seconds=case_timeout,
        suite_timeout_seconds=max(case_timeout + 15.0, cfg.java_suite_timeout_seconds),
    )
    if suite.status == "skipped":
        return JavaRunResult(
            status="skipped",
            exit_code=None,
            stdout="",
            stderr="",
            detail=suite.detail,
        )
    if not suite.results:
        return JavaRunResult(
            status="error",
            exit_code=None,
            stdout="",
            stderr="",
            detail=suite.detail or "empty_suite",
        )
    first = suite.results[0]
    return JavaRunResult(
        status=first.status,
        exit_code=first.exit_code,
        stdout=first.stdout,
        stderr=first.stderr,
        detail=first.detail,
    )


def run_java_test_suite(
    *,
    source: str,
    cases: tuple[JavaSuiteCase, ...] | list[JavaSuiteCase],
    main_class: str | None = None,
    variant_label: str = "code",
    settings: Settings | None = None,
    case_timeout_seconds: float | None = None,
    suite_timeout_seconds: float | None = None,
) -> JavaSuiteResult:
    """Один Docker-контейнер на вариант кода: compile once + все тесты, затем удаление."""
    cfg = settings or get_settings()
    case_list = tuple(cases)
    if not case_list:
        return JavaSuiteResult(
            status="error",
            detail="empty_cases",
            container_name=None,
            results=(),
        )
    if not docker_available():
        return JavaSuiteResult(
            status="skipped",
            detail="docker_unavailable",
            container_name=None,
            results=tuple(
                JavaSuiteCaseResult(
                    case_id=case.case_id,
                    status="skipped",
                    exit_code=None,
                    stdout="",
                    stderr="",
                    detail="docker_unavailable",
                )
                for case in case_list
            ),
        )

    class_name = detect_main_class(source, main_class)
    if not _SAFE_CLASS_RE.fullmatch(class_name):
        return JavaSuiteResult(
            status="error",
            detail="invalid_main_class",
            container_name=None,
            results=tuple(
                JavaSuiteCaseResult(
                    case_id=case.case_id,
                    status="error",
                    exit_code=None,
                    stdout="",
                    stderr="",
                    detail="invalid_main_class",
                )
                for case in case_list
            ),
        )

    case_timeout = (
        case_timeout_seconds if case_timeout_seconds is not None else cfg.java_case_timeout_seconds
    )
    # Полный TTL из настроек: большой исходник может долго компилироваться.
    suite_timeout = (
        suite_timeout_seconds
        if suite_timeout_seconds is not None
        else cfg.java_suite_timeout_seconds
    )
    suite_timeout = max(15.0, min(suite_timeout, cfg.java_suite_timeout_seconds))

    safe_label = re.sub(r"[^a-zA-Z0-9_.-]", "-", variant_label)[:24] or "code"
    run_id = f"{safe_label}-{uuid.uuid4().hex[:12]}"
    container_name = f"jb-java-{run_id}"

    with _open_java_work_dir(cfg, run_id=run_id) as work:
        _prepare_work_dir(
            work=work,
            source=source,
            class_name=class_name,
            cases=case_list,
            case_timeout=case_timeout,
        )
        try:
            return _execute_named_container(
                work=work,
                run_id=run_id,
                class_name=class_name,
                case_timeout=case_timeout,
                suite_timeout=suite_timeout,
                container_name=container_name,
                cases=case_list,
                settings=cfg,
            )
        finally:
            _force_remove_container(container_name)


@contextlib.contextmanager
def _open_java_work_dir(settings: Settings, *, run_id: str) -> Iterator[Path]:
    """Каталог исходников для JDK-контейнера.

    На хосте - TemporaryDirectory + bind mount.
    В Compose - подкаталог общего named volume (daemon не видит /tmp Backend).
    """
    if settings.java_work_dir is not None:
        root = settings.java_work_dir
        root.mkdir(parents=True, exist_ok=True)
        work = root / run_id
        work.mkdir(parents=True, exist_ok=False)
        # JDK-контейнер идёт под uid 1000 - нужен доступ на запись в эфемерный каталог.
        with contextlib.suppress(OSError):
            work.chmod(0o777)
        try:
            yield work
        finally:
            shutil.rmtree(work, ignore_errors=True)
        return

    with tempfile.TemporaryDirectory(prefix="jb_java_") as tmp:
        yield Path(tmp)


def _prepare_work_dir(
    *,
    work: Path,
    source: str,
    class_name: str,
    cases: tuple[JavaSuiteCase, ...],
    case_timeout: float,
) -> None:
    (work / f"{class_name}.java").write_text(source, encoding="utf-8")
    script_path = work / "run_suite.sh"
    script_path.write_text(_SUITE_SCRIPT, encoding="utf-8", newline="\n")
    # На Linux/macOS полезен +x; на Windows Docker вызываем через bash явно.
    with contextlib.suppress(OSError):
        script_path.chmod(0o755)
    for index, case in enumerate(cases):
        (work / f"case_{index}.in").write_text(case.stdin_text, encoding="utf-8")
    # Метаданные для отладки на хосте (не секреты).
    (work / "suite.meta").write_text(
        f"cases={len(cases)}\ncase_timeout={case_timeout}\n",
        encoding="utf-8",
    )


def _execute_named_container(
    *,
    work: Path,
    run_id: str,
    class_name: str,
    case_timeout: float,
    suite_timeout: float,
    container_name: str,
    cases: tuple[JavaSuiteCase, ...],
    settings: Settings,
) -> JavaSuiteResult:
    # case_timeout как целое число секунд для GNU timeout внутри контейнера.
    case_timeout_int = max(1, int(case_timeout))
    if settings.java_docker_work_volume:
        # Named volume: Backend и JDK-контейнер видят одни и те же файлы.
        volume_arg = f"{settings.java_docker_work_volume}:/work:rw"
        container_workdir = f"/work/{run_id}"
        script_path = f"{container_workdir}/run_suite.sh"
    else:
        volume_arg = f"{work.resolve()}:/work:rw"
        container_workdir = "/work"
        script_path = "/work/run_suite.sh"
    cmd = [
        "docker",
        "run",
        "--name",
        container_name,
        "--rm",
        "--network",
        "none",
        "--memory",
        settings.java_docker_memory,
        "--memory-swap",
        settings.java_docker_memory,
        "--cpus",
        settings.java_docker_cpus,
        "--pids-limit",
        str(settings.java_docker_pids_limit),
        "--user",
        "1000:1000",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,exec,nosuid,size=64m",  # noqa: S108 - tmpfs только внутри контейнера
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "-v",
        volume_arg,
        "-w",
        container_workdir,
        settings.java_docker_image,
        "bash",
        script_path,
        class_name,
        str(case_timeout_int),
    ]
    try:
        # Аргументы фиксированы; пользовательский код только в файлах /work.
        completed = subprocess.run(  # noqa: S603
            cmd,
            capture_output=True,
            timeout=suite_timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.warning(
            "java suite container TTL exceeded name=%s timeout=%.1f",
            container_name,
            suite_timeout,
        )
        _force_remove_container(container_name)
        return JavaSuiteResult(
            status="timeout",
            detail="container_ttl_exceeded",
            container_name=container_name,
            results=tuple(
                JavaSuiteCaseResult(
                    case_id=case.case_id,
                    status="fail",
                    exit_code=None,
                    stdout="",
                    stderr="",
                    detail="container_ttl_exceeded",
                )
                for case in cases
            ),
        )
    except OSError as exc:
        return JavaSuiteResult(
            status="error",
            detail=f"os_error:{type(exc).__name__}",
            container_name=container_name,
            results=tuple(
                JavaSuiteCaseResult(
                    case_id=case.case_id,
                    status="error",
                    exit_code=None,
                    stdout="",
                    stderr="",
                    detail=f"os_error:{type(exc).__name__}",
                )
                for case in cases
            ),
        )

    docker_stderr = completed.stderr.decode("utf-8", errors="replace")[:_MAX_OUTPUT]
    return _read_suite_results(
        work=work,
        cases=cases,
        docker_returncode=completed.returncode,
        docker_stderr=docker_stderr,
        container_name=container_name,
    )


def _read_suite_results(
    *,
    work: Path,
    cases: tuple[JavaSuiteCase, ...],
    docker_returncode: int,
    docker_stderr: str,
    container_name: str,
) -> JavaSuiteResult:
    compile_exit = _read_int_file(work / "compile.exit")
    suite_status = _read_text_file(work / "suite.status").strip()

    if compile_exit is None and suite_status == "":
        detail = "docker_failed" if docker_returncode != 0 else "suite_no_output"
        if docker_stderr:
            detail = f"{detail}:{docker_stderr[:200]}"
        return JavaSuiteResult(
            status="error",
            detail=detail,
            container_name=container_name,
            results=tuple(
                JavaSuiteCaseResult(
                    case_id=case.case_id,
                    status="error",
                    exit_code=None,
                    stdout="",
                    stderr=docker_stderr[:2000],
                    detail=detail,
                )
                for case in cases
            ),
        )

    if compile_exit is not None and compile_exit != 0:
        compile_err = _read_text_file(work / "compile.err")[:_MAX_OUTPUT]
        compile_out = _read_text_file(work / "compile.out")[:_MAX_OUTPUT]
        return JavaSuiteResult(
            status="error",
            detail="compile_error",
            container_name=container_name,
            results=tuple(
                JavaSuiteCaseResult(
                    case_id=case.case_id,
                    status="error",
                    exit_code=compile_exit,
                    stdout=compile_out,
                    stderr=compile_err,
                    detail="compile_error",
                )
                for case in cases
            ),
        )

    results: list[JavaSuiteCaseResult] = []
    for index, case in enumerate(cases):
        exit_code = _read_int_file(work / f"case_{index}.exit")
        stdout = _read_text_file(work / f"case_{index}.out")[:_MAX_OUTPUT]
        stderr = _read_text_file(work / f"case_{index}.err")[:_MAX_OUTPUT]
        if exit_code is None:
            results.append(
                JavaSuiteCaseResult(
                    case_id=case.case_id,
                    status="error",
                    exit_code=None,
                    stdout=stdout,
                    stderr=stderr,
                    detail="missing_case_result",
                )
            )
            continue
        # GNU timeout при убийстве процесса возвращает 124 / 137.
        if exit_code in {124, 137}:
            results.append(
                JavaSuiteCaseResult(
                    case_id=case.case_id,
                    status="fail",
                    exit_code=exit_code,
                    stdout=stdout,
                    stderr=stderr,
                    detail="case_timeout",
                )
            )
            continue
        results.append(
            JavaSuiteCaseResult(
                case_id=case.case_id,
                status="pass" if exit_code == 0 else "fail",
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                detail="ok" if exit_code == 0 else "nonzero_exit",
            )
        )

    return JavaSuiteResult(
        status="ok",
        detail="ok",
        container_name=container_name,
        results=tuple(results),
    )


def _force_remove_container(container_name: str) -> None:
    """Гарантированное удаление контейнера после TTL или сбоя docker CLI."""
    if not container_name:
        return
    try:
        subprocess.run(  # noqa: S603
            ["docker", "rm", "-f", container_name],  # noqa: S607
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        logger.warning("failed to force-remove container name=%s", container_name)


def _read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _read_int_file(path: Path) -> int | None:
    raw = _read_text_file(path).strip()
    if not raw:
        return None
    try:
        return int(raw.split()[0])
    except ValueError:
        return None
