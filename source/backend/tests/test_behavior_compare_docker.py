"""Сравнение версий: два Docker-suite (original / repaired), без реального Docker."""

from __future__ import annotations

from app.execution.java_runner import JavaSuiteCaseResult, JavaSuiteResult
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
    monkeypatch.setattr(bc, "generate_behavior_tests", lambda **_kwargs: scripts)

    calls: list[str] = []

    def fake_suite(*, source: str, cases, main_class, variant_label, **_kwargs):
        del source, main_class
        calls.append(variant_label)
        assert len(cases) == 2
        # original совпадает с эталоном; repaired падает на втором.
        if variant_label == "original":
            results = (
                JavaSuiteCaseResult("t1", "pass", 0, "1", "", "ok"),
                JavaSuiteCaseResult("t2", "pass", 0, "2", "", "ok"),
            )
        else:
            results = (
                JavaSuiteCaseResult("t1", "pass", 0, "1", "", "ok"),
                JavaSuiteCaseResult("t2", "fail", 1, "x", "", "nonzero_exit"),
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
    )
    assert calls == ["original", "repaired"]
    assert result.execution_available is True
    assert result.original_passed == 2
    assert result.generated_passed == 1
    assert result.regressions == 1
    assert any("docker_suite_original=ok:" in note for note in result.notes)
    assert any("docker_suite_repaired=ok:" in note for note in result.notes)
    assert "isolation=docker_one_container_per_variant" in result.report_lines
