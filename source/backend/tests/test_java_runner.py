"""Юнит-тесты изолированного Docker-раннера Java (без реального Docker)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from app.core.config import Settings
from app.execution import java_runner as jr


def _work_dir_from_docker_cmd(cmd: list[str]) -> Path:
    """Извлекает host-путь из `-v path:/work:rw` (устойчиво к диску C: на Windows)."""
    volume = cmd[cmd.index("-v") + 1]
    suffix = ":/work:rw"
    assert volume.endswith(suffix), volume
    return Path(volume[: -len(suffix)])


@pytest.fixture
def java_settings() -> Settings:
    return Settings(
        _env_file=None,
        java_docker_image="eclipse-temurin:21-jdk",
        java_docker_memory="384m",
        java_docker_cpus="1.0",
        java_docker_pids_limit=64,
        java_suite_timeout_seconds=300.0,
        java_case_timeout_seconds=30.0,
    )


def test_docker_unavailable_skips_suite(
    monkeypatch: pytest.MonkeyPatch, java_settings: Settings
) -> None:
    monkeypatch.setattr(jr, "docker_available", lambda: False)
    result = jr.run_java_test_suite(
        source="class Main { public static void main(String[] a) {} }",
        cases=(jr.JavaSuiteCase(case_id="t1", stdin_text=""),),
        variant_label="original",
        settings=java_settings,
    )
    assert result.status == "skipped"
    assert result.detail == "docker_unavailable"
    assert result.results[0].status == "skipped"


def test_suite_reads_case_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    java_settings: Settings,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(jr, "docker_available", lambda: True)

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        # Имитируем docker run: артефакты уже лежат в смонтированном /work.
        work = _work_dir_from_docker_cmd(cmd)
        (work / "compile.exit").write_text("0\n", encoding="utf-8")
        (work / "suite.status").write_text("DONE\n", encoding="utf-8")
        (work / "case_0.exit").write_text("0\n", encoding="utf-8")
        (work / "case_0.out").write_text("hello\n", encoding="utf-8")
        (work / "case_0.err").write_text("", encoding="utf-8")
        (work / "case_1.exit").write_text("1\n", encoding="utf-8")
        (work / "case_1.out").write_text("bad\n", encoding="utf-8")
        (work / "case_1.err").write_text("err\n", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    removed: list[str] = []

    def fake_remove(name: str) -> None:
        removed.append(name)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(jr, "_force_remove_container", fake_remove)

    result = jr.run_java_test_suite(
        source="class Main { public static void main(String[] a) {} }",
        cases=(
            jr.JavaSuiteCase(case_id="a", stdin_text="1"),
            jr.JavaSuiteCase(case_id="b", stdin_text="2"),
        ),
        variant_label="repaired",
        settings=java_settings,
    )
    assert result.status == "ok"
    assert result.container_name is not None
    assert result.container_name.startswith("jb-java-repaired-")
    assert result.results[0].status == "pass"
    assert result.results[0].stdout.strip() == "hello"
    assert result.results[1].status == "fail"
    assert result.results[1].exit_code == 1
    # Контейнер всегда удаляется в finally.
    assert removed == [result.container_name]


def test_suite_ttl_force_removes_container(
    monkeypatch: pytest.MonkeyPatch,
    java_settings: Settings,
) -> None:
    monkeypatch.setattr(jr, "docker_available", lambda: True)

    def boom(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout", 1))

    removed: list[str] = []

    def fake_remove(name: str) -> None:
        removed.append(name)

    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(jr, "_force_remove_container", fake_remove)

    result = jr.run_java_test_suite(
        source="class Main { public static void main(String[] a) {} }",
        cases=(jr.JavaSuiteCase(case_id="t1", stdin_text=""),),
        variant_label="original",
        settings=java_settings,
        suite_timeout_seconds=15.0,
    )
    assert result.status == "timeout"
    assert result.detail == "container_ttl_exceeded"
    assert result.results[0].detail == "container_ttl_exceeded"
    # Удаление и из обработчика TTL, и из finally.
    assert result.container_name in removed
    assert removed.count(result.container_name) >= 1


def test_compile_error_propagates_to_all_cases(
    monkeypatch: pytest.MonkeyPatch,
    java_settings: Settings,
) -> None:
    monkeypatch.setattr(jr, "docker_available", lambda: True)

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        work = _work_dir_from_docker_cmd(cmd)
        (work / "compile.exit").write_text("1\n", encoding="utf-8")
        (work / "compile.err").write_text("error: cannot find symbol\n", encoding="utf-8")
        (work / "suite.status").write_text("COMPILE_FAIL\n", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(jr, "_force_remove_container", lambda _name: None)

    result = jr.run_java_test_suite(
        source="class Broken {",
        cases=(
            jr.JavaSuiteCase(case_id="a", stdin_text=""),
            jr.JavaSuiteCase(case_id="b", stdin_text=""),
        ),
        variant_label="original",
        settings=java_settings,
    )
    assert result.status == "error"
    assert result.detail == "compile_error"
    assert all(row.detail == "compile_error" for row in result.results)


def test_named_container_uses_isolation_flags(
    monkeypatch: pytest.MonkeyPatch,
    java_settings: Settings,
) -> None:
    monkeypatch.setattr(jr, "docker_available", lambda: True)
    captured: dict[str, Any] = {}

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        captured["cmd"] = cmd
        work = _work_dir_from_docker_cmd(cmd)
        (work / "compile.exit").write_text("0\n", encoding="utf-8")
        (work / "suite.status").write_text("DONE\n", encoding="utf-8")
        (work / "case_0.exit").write_text("0\n", encoding="utf-8")
        (work / "case_0.out").write_text("", encoding="utf-8")
        (work / "case_0.err").write_text("", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(jr, "_force_remove_container", lambda _name: None)

    jr.run_java_test_suite(
        source="class Main { public static void main(String[] a) {} }",
        cases=(jr.JavaSuiteCase(case_id="t1", stdin_text=""),),
        variant_label="original",
        settings=java_settings,
    )
    cmd = captured["cmd"]
    assert "--network" in cmd and "none" in cmd
    assert "--read-only" in cmd
    assert "--cap-drop" in cmd and "ALL" in cmd
    assert "--rm" in cmd
    assert "--name" in cmd
    assert "bash" in cmd and "/work/run_suite.sh" in cmd


def test_named_volume_uses_shared_workdir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Compose-режим: named volume + подкаталог run_id, не bind /tmp контейнера."""
    monkeypatch.setattr(jr, "docker_available", lambda: True)
    settings = Settings(
        _env_file=None,
        java_docker_image="eclipse-temurin:21-jdk",
        java_docker_memory="384m",
        java_docker_cpus="1.0",
        java_docker_pids_limit=64,
        java_suite_timeout_seconds=300.0,
        java_case_timeout_seconds=30.0,
        java_work_dir=tmp_path,
        java_docker_work_volume="jb-java-work",
    )
    captured: dict[str, Any] = {}

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        del kwargs
        captured["cmd"] = cmd
        # Файлы лежат на общем volume (tmp_path/run_id), не в bind mount аргументе.
        work_dirs = [path for path in tmp_path.iterdir() if path.is_dir()]
        assert len(work_dirs) == 1
        work = work_dirs[0]
        (work / "compile.exit").write_text("0\n", encoding="utf-8")
        (work / "suite.status").write_text("DONE\n", encoding="utf-8")
        (work / "case_0.exit").write_text("0\n", encoding="utf-8")
        (work / "case_0.out").write_text("ok\n", encoding="utf-8")
        (work / "case_0.err").write_text("", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(jr, "_force_remove_container", lambda _name: None)

    result = jr.run_java_test_suite(
        source="class Main { public static void main(String[] a) {} }",
        cases=(jr.JavaSuiteCase(case_id="t1", stdin_text=""),),
        variant_label="original",
        settings=settings,
    )
    cmd = captured["cmd"]
    assert "jb-java-work:/work:rw" in cmd
    assert "-w" in cmd
    workdir = cmd[cmd.index("-w") + 1]
    assert workdir.startswith("/work/")
    assert f"{workdir}/run_suite.sh" in cmd
    assert result.status == "ok"
    assert result.results[0].stdout.strip() == "ok"
