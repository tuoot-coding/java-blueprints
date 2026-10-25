"""Доп. проверки: hint без class и обёртка unnamed-фрагмента."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from app.core.config import Settings
from app.execution import java_runner as jr


def test_detect_main_class_ignores_stale_hint_when_other_class_exists() -> None:
    source = "class Foo { public static void main(String[] a) {} }"
    assert jr.detect_main_class(source, "StructuralTest") == "Foo"


def test_detect_main_class_uses_hint_only_as_wrapper_name_for_fragment() -> None:
    fragment = "public static void main(String[] args) { System.out.println(1); }"
    assert jr.detect_main_class(fragment, "StructuralTest") == "StructuralTest"


def test_ensure_named_compilation_unit_wraps_top_level_main() -> None:
    fragment = "public static void main(String[] args) { System.out.println(1); }"
    wrapped = jr.ensure_named_compilation_unit(fragment, "StructuralTest")
    assert wrapped.startswith("public class StructuralTest {")
    assert "public static void main" in wrapped
    assert jr._TYPE_DECL_RE.search(wrapped)


def test_ensure_named_compilation_unit_keeps_existing_class() -> None:
    source = "class Keep { public static void main(String[] a) {} }\n"
    assert jr.ensure_named_compilation_unit(source, "Keep") == source


def test_suite_writes_wrapped_source_for_unnamed_fragment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Фрагмент с голым main не уходит в javac как unnamed class."""
    monkeypatch.setattr(jr, "docker_available", lambda: True)
    written: dict[str, str] = {}

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        del kwargs
        volume = cmd[cmd.index("-v") + 1]
        work = Path(volume[: -len(":/work:rw")])
        java_files = list(work.glob("*.java"))
        assert len(java_files) == 1
        written["name"] = java_files[0].name
        written["text"] = java_files[0].read_text(encoding="utf-8")
        (work / "compile.exit").write_text("0\n", encoding="utf-8")
        (work / "suite.status").write_text("DONE\n", encoding="utf-8")
        (work / "case_0.exit").write_text("0\n", encoding="utf-8")
        (work / "case_0.out").write_text("1\n", encoding="utf-8")
        (work / "case_0.err").write_text("", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(jr, "_force_remove_container", lambda _name: None)

    settings = Settings(
        _env_file=None,
        java_docker_image="eclipse-temurin:21-jdk",
        java_docker_memory="384m",
        java_docker_cpus="1.0",
        java_docker_pids_limit=64,
        java_suite_timeout_seconds=300.0,
        java_case_timeout_seconds=30.0,
    )
    fragment = "public static void main(String[] args) { System.out.println(1); }"
    result = jr.run_java_test_suite(
        source=fragment,
        cases=(jr.JavaSuiteCase(case_id="t01", stdin_text=""),),
        main_class="StructuralTest",
        variant_label="original",
        settings=settings,
    )
    assert result.status == "ok"
    assert written["name"] == "StructuralTest.java"
    assert "public class StructuralTest" in written["text"]
    assert "unnamed" not in written["text"].lower()
