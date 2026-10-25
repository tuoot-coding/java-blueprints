"""Сравнение двух Java-версий по LLM-тестам (stdin/stdout) и метрикам.

Каждый вариант кода (original / generated) выполняется в отдельном
Docker-контейнере: compile once + все тесты, затем принудительное удаление.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from app.core.logging import log_activity
from app.execution.java_runner import (
    JavaSuiteCase,
    JavaSuiteCaseResult,
    docker_available,
    run_java_test_suite,
)
from app.llm.call_options import LlmCallOptions
from app.llm.test_scripts import BehaviorTestCase, generate_behavior_tests
from app.services.code_compare import CodeCompareMetrics, compare_generated_to_original


@dataclass(frozen=True, slots=True)
class BehaviorTestRunRow:
    test_id: str
    name: str
    original_status: str
    generated_status: str
    original_exit_code: int | None
    generated_exit_code: int | None
    original_stdout: str
    generated_stdout: str
    expected_stdout: str
    matched_expected_original: bool
    matched_expected_generated: bool
    detail: str


@dataclass(frozen=True, slots=True)
class BehaviorCompareResult:
    execution_available: bool
    execution_reason: str | None
    tests: tuple[BehaviorTestCase, ...]
    runs: tuple[BehaviorTestRunRow, ...]
    original_passed: int
    generated_passed: int
    regressions: int
    improvements: int
    score: float
    passed: bool
    report_lines: tuple[str, ...]
    code_metrics: CodeCompareMetrics | None
    notes: tuple[str, ...]


def compare_versions_with_tests(
    *,
    original: str,
    generated: str,
    options: LlmCallOptions | None,
) -> BehaviorCompareResult:
    """Сначала генерирует 10 тестов по original, затем гоняет обе версии в Docker."""
    started = time.perf_counter()
    notes: list[str] = []
    tests: tuple[BehaviorTestCase, ...] = ()
    if options is None:
        notes.append("llm_not_configured_for_tests")
        test_status = "unavailable"
        test_reason = "llm_not_configured"
    else:
        scripts = generate_behavior_tests(source=original, options=options, count=10)
        tests = scripts.tests
        notes.extend(scripts.notes)
        test_status = scripts.status
        test_reason = scripts.error_reason
        if scripts.status != "ok":
            notes.append(f"test_scripts_{scripts.status}")

    can_run = docker_available()
    execution_reason = None if can_run else "docker_unavailable"
    runs: list[BehaviorTestRunRow] = []
    original_passed = 0
    generated_passed = 0
    regressions = 0
    improvements = 0

    if can_run and tests:
        suite_cases = tuple(JavaSuiteCase(case_id=case.id, stdin_text=case.stdin) for case in tests)
        # Подсказка main-класса: берем первую непустую из сценариев.
        main_hint = next(
            (case.main_class_hint for case in tests if case.main_class_hint),
            None,
        )
        # Два изолированных контейнера: исходный и восстановленный код.
        orig_suite = run_java_test_suite(
            source=original,
            cases=suite_cases,
            main_class=main_hint,
            variant_label="original",
        )
        gen_suite = run_java_test_suite(
            source=generated,
            cases=suite_cases,
            main_class=main_hint,
            variant_label="repaired",
        )
        notes.append(
            f"docker_suite_original={orig_suite.status}:{orig_suite.detail}:"
            f"{orig_suite.container_name or '-'}"
        )
        notes.append(
            f"docker_suite_repaired={gen_suite.status}:{gen_suite.detail}:"
            f"{gen_suite.container_name or '-'}"
        )
        if orig_suite.status == "timeout" or gen_suite.status == "timeout":
            notes.append("docker_container_ttl_exceeded")
        if orig_suite.status == "error" or gen_suite.status == "error":
            notes.append("docker_suite_failed_see_run_details")

        orig_by_id = {row.case_id: row for row in orig_suite.results}
        gen_by_id = {row.case_id: row for row in gen_suite.results}

        for case in tests:
            orig_run = orig_by_id.get(case.id) or JavaSuiteCaseResult(
                case_id=case.id,
                status="error",
                exit_code=None,
                stdout="",
                stderr="",
                detail="missing_original_result",
            )
            gen_run = gen_by_id.get(case.id) or JavaSuiteCaseResult(
                case_id=case.id,
                status="error",
                exit_code=None,
                stdout="",
                stderr="",
                detail="missing_generated_result",
            )
            orig_match = _matches_expectation(orig_run.stdout, case.expected_stdout) and (
                orig_run.exit_code == case.expected_exit_code
                if orig_run.exit_code is not None
                else False
            )
            gen_match = _matches_expectation(gen_run.stdout, case.expected_stdout) and (
                gen_run.exit_code == case.expected_exit_code
                if gen_run.exit_code is not None
                else False
            )
            # pass = совпало с эталоном LLM; иначе статус раннера.
            orig_status = (
                "pass" if orig_match else (orig_run.status if orig_run.status != "pass" else "fail")
            )
            gen_status = (
                "pass" if gen_match else (gen_run.status if gen_run.status != "pass" else "fail")
            )
            if orig_status == "pass":
                original_passed += 1
            if gen_status == "pass":
                generated_passed += 1
            if orig_status == "pass" and gen_status != "pass":
                regressions += 1
            if orig_status != "pass" and gen_status == "pass":
                improvements += 1
            runs.append(
                BehaviorTestRunRow(
                    test_id=case.id,
                    name=case.name,
                    original_status=orig_status,
                    generated_status=gen_status,
                    original_exit_code=orig_run.exit_code,
                    generated_exit_code=gen_run.exit_code,
                    original_stdout=orig_run.stdout[-2000:],
                    generated_stdout=gen_run.stdout[-2000:],
                    expected_stdout=case.expected_stdout[-2000:],
                    matched_expected_original=orig_match,
                    matched_expected_generated=gen_match,
                    detail=f"orig={orig_run.detail};gen={gen_run.detail}",
                )
            )
    elif tests and not can_run:
        notes.append("tests_not_executed_docker_unavailable")
        for case in tests:
            runs.append(
                BehaviorTestRunRow(
                    test_id=case.id,
                    name=case.name,
                    original_status="skipped",
                    generated_status="skipped",
                    original_exit_code=None,
                    generated_exit_code=None,
                    original_stdout="",
                    generated_stdout="",
                    expected_stdout=case.expected_stdout[-2000:],
                    matched_expected_original=False,
                    matched_expected_generated=False,
                    detail="docker_unavailable",
                )
            )

    code_metrics = compare_generated_to_original(original, generated)
    total = max(len(tests), 1)
    if can_run and tests:
        score = generated_passed / total
        # Регрессии сильно штрафуют.
        score = max(0.0, score - 0.08 * regressions)
        passed = (
            regressions == 0
            and generated_passed >= original_passed
            and generated_passed >= max(1, total // 2)
        )
    else:
        # Без исполнения опираемся на структурные метрики кода.
        score = code_metrics.score
        passed = code_metrics.passed and test_status in {"ok", "unavailable"}
        notes.append("score_from_code_metrics_without_execution")

    elapsed_ms = (time.perf_counter() - started) * 1000.0
    report = (
        f"elapsed_ms={elapsed_ms:.1f}",
        f"tests={len(tests)} status={test_status}",
        f"execution_available={can_run} reason={execution_reason or test_reason or '-'}",
        "isolation=docker_one_container_per_variant",
        f"passed original={original_passed} generated={generated_passed}",
        f"regressions={regressions} improvements={improvements}",
        f"score={score:.3f} passed={passed}",
        *code_metrics.report_lines[:4],
    )
    log_activity(
        "behavior_compare_done",
        tests=len(tests),
        can_run=can_run,
        generated_passed=generated_passed,
        regressions=regressions,
        score=round(score, 3),
    )
    return BehaviorCompareResult(
        execution_available=can_run,
        execution_reason=execution_reason,
        tests=tests,
        runs=tuple(runs),
        original_passed=original_passed,
        generated_passed=generated_passed,
        regressions=regressions,
        improvements=improvements,
        score=score,
        passed=passed,
        report_lines=report,
        code_metrics=code_metrics,
        notes=tuple(notes),
    )


def _matches_expectation(actual: str, expected: str) -> bool:
    left = actual.replace("\r\n", "\n").strip()
    right = expected.replace("\r\n", "\n").strip()
    if not right:
        return True
    return left == right or left.endswith(right) or right in left
