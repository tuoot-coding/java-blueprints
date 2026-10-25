"""Сравнение версий: два Docker-suite (original / repaired), без реального Docker."""

from __future__ import annotations

from app.execution.java_runner import JavaCaseResourceMetrics, JavaSuiteCaseResult, JavaSuiteResult
from app.llm import test_scripts as test_scripts_mod
from app.services import behavior_compare as bc


def test_compare_runs_two_isolated_suites(monkeypatch) -> None:
    monkeypatch.setattr(bc, "docker_available", lambda: True)

    scripts = test_scripts_mod.TestScriptsResult(
        status="ok",
        error_reason=None,
        notes=(),
        model="test-model",
        tests=(
            test_scripts_mod.BehaviorTestCase(
                id="t1",
                name="one",
                stdin="1\n",
                expected_stdout="1",
                expected_exit_code=0,
                main_class_hint="Main",
            ),
            test_scripts_mod.BehaviorTestCase(
                id="t2",
                name="two",
                stdin="2\n",
                expected_stdout="2",
                expected_exit_code=0,
                main_class_hint="Main",
            ),
        ),
    )
    captured: dict[str, object] = {}

    def fake_generate(**kwargs):
        captured["known_issues"] = kwargs.get("known_issues")
        return scripts

    monkeypatch.setattr(bc, "generate_behavior_tests", fake_generate)

    calls: list[str] = []

    def fake_suite(*, source: str, cases, main_class, variant_label, **_kwargs):
        del source, main_class
        calls.append(variant_label)
        assert len(cases) == 2
        metrics = JavaCaseResourceMetrics(wall_ms=12, cpu_user_ms=8, cpu_sys_ms=1, max_rss_kb=2048)
        if variant_label == "original":
            results = (
                JavaSuiteCaseResult("t1", "pass", 0, "1", "", "ok", metrics),
                JavaSuiteCaseResult("t2", "pass", 0, "2", "", "ok", metrics),
            )
        else:
            results = (
                JavaSuiteCaseResult("t1", "pass", 0, "1", "", "ok", metrics),
                JavaSuiteCaseResult("t2", "fail", 1, "x", "", "nonzero_exit", metrics),
            )
        return JavaSuiteResult(
            status="ok",
            detail="ok",
            container_name=f"jb-java-{variant_label}-test",
            results=results,
        )

    monkeypatch.setattr(bc, "run_java_test_suite", fake_suite)

    issues = [{"id": "e1", "severity": "error", "title": "bug", "message": "npe"}]
    result = bc.compare_versions_with_tests(
        original="class Main {}",
        generated="class Main {}",
        options=object(),  # type: ignore[arg-type]
        known_issues=issues,
    )
    assert captured["known_issues"] == issues
    assert calls == ["original", "repaired"]
    assert result.execution_available is True
    assert result.original_passed == 2
    assert result.generated_passed == 1
    assert result.regressions == 1
    assert result.runs[0].original_wall_ms == 12
    assert result.runs[0].generated_max_rss_kb == 2048
    assert any("docker_suite_original=ok:" in note for note in result.notes)
    assert any("docker_suite_repaired=ok:" in note for note in result.notes)
    assert any(note == "golden_from_original_stdout" for note in result.notes)
    assert "isolation=docker_one_container_per_variant" in result.report_lines
    assert "oracle=original_runtime_stdout" in result.report_lines
    assert result.tests[0].expected_stdout == "1"
    assert result.runs[0].matched_expected_generated is True
    assert result.runs[1].matched_expected_generated is False


def test_compare_ignores_wrong_llm_expected(monkeypatch) -> None:
    """Даже при неверном expected от LLM original остаётся pass после калибровки."""
    monkeypatch.setattr(bc, "docker_available", lambda: True)
    scripts = test_scripts_mod.TestScriptsResult(
        status="ok",
        error_reason=None,
        notes=(),
        model="test-model",
        tests=(
            test_scripts_mod.BehaviorTestCase(
                id="t1",
                name="one",
                stdin="1\n",
                expected_stdout="WRONG",
                expected_exit_code=0,
                main_class_hint="Main",
            ),
        ),
    )
    monkeypatch.setattr(bc, "generate_behavior_tests", lambda **_kwargs: scripts)

    def fake_suite(*, source: str, cases, main_class, variant_label, **_kwargs):
        del source, cases, main_class
        return JavaSuiteResult(
            status="ok",
            detail="ok",
            container_name=f"jb-java-{variant_label}-test",
            results=(JavaSuiteCaseResult("t1", "pass", 0, "hello\n", "", "ok"),),
        )

    monkeypatch.setattr(bc, "run_java_test_suite", fake_suite)
    result = bc.compare_versions_with_tests(
        original="class Main {}",
        generated="class Main {}",
        options=object(),  # type: ignore[arg-type]
    )
    assert result.original_passed == 1
    assert result.generated_passed == 1
    assert result.tests[0].expected_stdout == "hello\n"


def test_compare_shows_fail_and_resources_when_original_crashes(monkeypatch) -> None:
    """Провал original - статус fail с метриками, не invalid_script."""
    monkeypatch.setattr(bc, "docker_available", lambda: True)
    scripts = test_scripts_mod.TestScriptsResult(
        status="ok",
        error_reason=None,
        notes=(),
        model="test-model",
        tests=(
            test_scripts_mod.BehaviorTestCase(
                id="t1",
                name="bad_stdin",
                stdin="oops\n",
                expected_stdout="",
                expected_exit_code=0,
                purpose="workability",
                description="Граничный ввод",
                error_description="",
            ),
        ),
    )
    monkeypatch.setattr(bc, "generate_behavior_tests", lambda **_kwargs: scripts)

    def fake_suite(*, source: str, cases, main_class, variant_label, **_kwargs):
        del source, cases, main_class
        metrics = JavaCaseResourceMetrics(
            wall_ms=20, cpu_user_ms=5, cpu_sys_ms=1, max_rss_kb=1000
        )
        if variant_label == "original":
            return JavaSuiteResult(
                status="ok",
                detail="ok",
                container_name="jb-java-original-test",
                results=(
                    JavaSuiteCaseResult(
                        "t1",
                        "fail",
                        1,
                        "",
                        "Exception in thread main java.util.InputMismatchException",
                        "nonzero_exit",
                        metrics,
                    ),
                ),
            )
        return JavaSuiteResult(
            status="ok",
            detail="ok",
            container_name="jb-java-repaired-test",
            results=(
                JavaSuiteCaseResult("t1", "pass", 0, "ok\n", "", "ok", metrics),
            ),
        )

    monkeypatch.setattr(bc, "run_java_test_suite", fake_suite)
    result = bc.compare_versions_with_tests(
        original="class Main {}",
        generated="class Main {}",
        options=object(),  # type: ignore[arg-type]
    )
    assert result.runs[0].original_status == "fail"
    assert result.runs[0].generated_status == "pass"
    assert result.runs[0].original_wall_ms == 20
    assert result.runs[0].generated_max_rss_kb == 1000
    assert result.improvements == 1


def test_compare_exploit_marks_original_fail_and_repaired_pass(monkeypatch) -> None:
    """Exploit: original падает на баге, repaired проходит - improvement."""
    monkeypatch.setattr(bc, "docker_available", lambda: True)
    scripts = test_scripts_mod.TestScriptsResult(
        status="ok",
        error_reason=None,
        notes=("exploit_scenarios=1",),
        model="test-model",
        tests=(
            test_scripts_mod.BehaviorTestCase(
                id="t1",
                name="happy",
                stdin="1\n",
                expected_stdout="ok",
                expected_exit_code=0,
                purpose="workability",
            ),
            test_scripts_mod.BehaviorTestCase(
                id="t2",
                name="trigger_npe",
                stdin="null\n",
                expected_stdout="",
                expected_exit_code=1,
                purpose="exploit_error",
                related_issue_id="e1",
                expects_original_failure=True,
            ),
        ),
    )
    monkeypatch.setattr(bc, "generate_behavior_tests", lambda **_kwargs: scripts)

    def fake_suite(*, source: str, cases, main_class, variant_label, **_kwargs):
        del source, cases, main_class
        if variant_label == "original":
            results = (
                JavaSuiteCaseResult("t1", "pass", 0, "ok", "", "ok"),
                JavaSuiteCaseResult(
                    "t2",
                    "fail",
                    1,
                    "",
                    "Exception in thread main java.lang.NullPointerException",
                    "nonzero_exit",
                ),
            )
        else:
            results = (
                JavaSuiteCaseResult("t1", "pass", 0, "ok", "", "ok"),
                JavaSuiteCaseResult("t2", "pass", 0, "safe\n", "", "ok"),
            )
        return JavaSuiteResult(
            status="ok",
            detail="ok",
            container_name=f"jb-java-{variant_label}-test",
            results=results,
        )

    monkeypatch.setattr(bc, "run_java_test_suite", fake_suite)
    result = bc.compare_versions_with_tests(
        original="class Main {}",
        generated="class Main {}",
        options=object(),  # type: ignore[arg-type]
        known_issues=[{"id": "e1", "severity": "error", "title": "NPE", "message": "x"}],
    )
    assert result.runs[0].original_status == "pass"
    assert result.runs[0].generated_status == "pass"
    assert result.runs[1].purpose == "exploit_error"
    assert result.runs[1].original_status == "fail"
    assert result.runs[1].generated_status == "pass"
    assert result.runs[1].matched_expected_original is True
    assert result.runs[1].matched_expected_generated is True
    assert result.improvements == 1
    assert result.regressions == 0
    assert result.generated_passed == 2
