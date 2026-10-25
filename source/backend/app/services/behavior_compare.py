"""Сравнение двух Java-версий по LLM-тестам (stdin/stdout) и метрикам.

Порядок: генерация сценариев -> прогон на original (baseline stdout/exit/ресурсы)
-> прогон repaired -> сравнение поведения и ресурсов с ориентиром original.
Workability, не отрабатывающие на исходнике, помечаются как невалидные скрипты.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from app.core.logging import log_activity
from app.execution.java_runner import (
    JavaCaseResourceMetrics,
    JavaSuiteCase,
    JavaSuiteCaseResult,
    docker_available,
    run_java_test_suite,
)
from app.llm.call_options import LlmCallOptions
from app.llm.test_scripts import BehaviorTestCase, generate_behavior_tests
from app.services.code_compare import CodeCompareMetrics, compare_generated_to_original

# Ориентир: repaired не должен быть сильно тяжелее original.
_WALL_SLOW_RATIO = 3.0
_RSS_HEAVY_RATIO = 2.5


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
    purpose: str = "workability"
    related_issue_id: str | None = None
    expects_original_failure: bool = False
    description: str = ""
    error_description: str = ""
    original_stderr: str = ""
    generated_stderr: str = ""
    original_wall_ms: int | None = None
    original_cpu_user_ms: int | None = None
    original_cpu_sys_ms: int | None = None
    original_max_rss_kb: int | None = None
    generated_wall_ms: int | None = None
    generated_cpu_user_ms: int | None = None
    generated_cpu_sys_ms: int | None = None
    generated_max_rss_kb: int | None = None
    wall_ratio: float | None = None
    cpu_ratio: float | None = None
    rss_ratio: float | None = None
    resources_vs_baseline: str = "n/a"


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
    known_issues: list[dict[str, Any]] | None = None,
) -> BehaviorCompareResult:
    """Сценарии -> baseline на original -> сравнение repaired с этим ориентиром."""
    started = time.perf_counter()
    notes: list[str] = []
    tests: tuple[BehaviorTestCase, ...] = ()
    issues = list(known_issues or [])
    if options is None:
        notes.append("llm_not_configured_for_tests")
        test_status = "unavailable"
        test_reason = "llm_not_configured"
    else:
        scripts = generate_behavior_tests(
            source=original,
            options=options,
            count=10,
            known_issues=issues,
        )
        tests = scripts.tests
        notes.extend(scripts.notes)
        test_status = scripts.status
        test_reason = scripts.error_reason
        notes.append(f"known_issues_for_tests={len(issues)}")
        if scripts.status != "ok":
            notes.append(f"test_scripts_{scripts.status}")

    can_run = docker_available()
    execution_reason = None if can_run else "docker_unavailable"
    runs: list[BehaviorTestRunRow] = []
    original_passed = 0
    generated_passed = 0
    regressions = 0
    improvements = 0
    calibrated_tests = tests

    if can_run and tests:
        suite_cases = tuple(JavaSuiteCase(case_id=case.id, stdin_text=case.stdin) for case in tests)
        main_hint = next(
            (case.main_class_hint for case in tests if case.main_class_hint),
            None,
        )
        # 1) Сначала original: stdout/exit/ресурсы = ориентир (baseline).
        orig_suite = run_java_test_suite(
            source=original,
            cases=suite_cases,
            main_class=main_hint,
            variant_label="original",
        )
        notes.append(
            f"docker_suite_original={orig_suite.status}:{orig_suite.detail}:"
            f"{orig_suite.container_name or '-'}"
        )
        notes.append("baseline_resources_from_original")

        # 2) Затем repaired на тех же stdin.
        gen_suite = run_java_test_suite(
            source=generated,
            cases=suite_cases,
            main_class=main_hint,
            variant_label="repaired",
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
        calibrated_list: list[BehaviorTestCase] = []
        notes.append("golden_from_original_stdout")

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
            golden_stdout = orig_run.stdout
            golden_exit = orig_run.exit_code
            calibrated_list.append(
                BehaviorTestCase(
                    id=case.id,
                    name=case.name,
                    stdin=case.stdin,
                    expected_stdout=golden_stdout,
                    expected_exit_code=golden_exit if golden_exit is not None else 0,
                    main_class_hint=case.main_class_hint,
                    purpose=case.purpose,
                    related_issue_id=case.related_issue_id,
                    expects_original_failure=case.expects_original_failure,
                    description=case.description,
                    error_description=case.error_description,
                )
            )

            orig_status, gen_status, orig_match, gen_match = _score_case(
                case=case,
                orig_run=orig_run,
                gen_run=gen_run,
            )

            if orig_status == "pass":
                original_passed += 1
            if gen_status == "pass":
                generated_passed += 1
            if orig_status == "pass" and gen_status != "pass":
                regressions += 1
            if orig_status != "pass" and gen_status == "pass":
                improvements += 1

            orig_m = orig_run.metrics
            gen_m = gen_run.metrics
            wall_ratio, cpu_ratio, rss_ratio, res_vs = _compare_resources(orig_m, gen_m)
            detail = _build_run_detail(
                case=case,
                orig_run=orig_run,
                gen_run=gen_run,
                orig_status=orig_status,
                gen_status=gen_status,
                wall_ratio=wall_ratio,
                cpu_ratio=cpu_ratio,
                rss_ratio=rss_ratio,
                resources_vs_baseline=res_vs,
            )
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
                    expected_stdout=golden_stdout[-2000:],
                    matched_expected_original=orig_match,
                    matched_expected_generated=gen_match,
                    detail=detail,
                    purpose=case.purpose,
                    related_issue_id=case.related_issue_id,
                    expects_original_failure=case.expects_original_failure,
                    description=case.description,
                    error_description=case.error_description,
                    original_stderr=(orig_run.stderr or "")[-1500:],
                    generated_stderr=(gen_run.stderr or "")[-1500:],
                    original_wall_ms=_m_wall(orig_m),
                    original_cpu_user_ms=_m_cpu_user(orig_m),
                    original_cpu_sys_ms=_m_cpu_sys(orig_m),
                    original_max_rss_kb=_m_rss(orig_m),
                    generated_wall_ms=_m_wall(gen_m),
                    generated_cpu_user_ms=_m_cpu_user(gen_m),
                    generated_cpu_sys_ms=_m_cpu_sys(gen_m),
                    generated_max_rss_kb=_m_rss(gen_m),
                    wall_ratio=wall_ratio,
                    cpu_ratio=cpu_ratio,
                    rss_ratio=rss_ratio,
                    resources_vs_baseline=res_vs,
                )
            )
        calibrated_tests = tuple(calibrated_list)
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
                    detail=case.error_description or case.description or "docker_unavailable",
                    purpose=case.purpose,
                    related_issue_id=case.related_issue_id,
                    expects_original_failure=case.expects_original_failure,
                    description=case.description,
                    error_description=case.error_description,
                )
            )

    code_metrics = compare_generated_to_original(original, generated)
    total = max(len(calibrated_tests), 1)
    if can_run and calibrated_tests:
        score = generated_passed / total
        score = max(0.0, score - 0.08 * regressions)
        passed = regressions == 0 and generated_passed >= max(1, total // 2)
    else:
        score = code_metrics.score
        passed = code_metrics.passed and test_status in {"ok", "unavailable"}
        notes.append("score_from_code_metrics_without_execution")

    elapsed_ms = (time.perf_counter() - started) * 1000.0
    exploit_n = sum(1 for case in calibrated_tests if case.expects_original_failure)
    report = (
        f"elapsed_ms={elapsed_ms:.1f}",
        f"tests={len(calibrated_tests)} status={test_status} exploit={exploit_n}",
        f"execution_available={can_run} reason={execution_reason or test_reason or '-'}",
        "isolation=docker_one_container_per_variant",
        "order=original_baseline_then_repaired",
        "oracle=original_runtime_stdout",
        "resources_baseline=original_wall_cpu_rss",
        f"passed original={original_passed} generated={generated_passed}",
        f"regressions={regressions} improvements={improvements}",
        f"score={score:.3f} passed={passed}",
        *code_metrics.report_lines[:4],
    )
    log_activity(
        "behavior_compare_done",
        tests=len(calibrated_tests),
        can_run=can_run,
        generated_passed=generated_passed,
        regressions=regressions,
        exploit=exploit_n,
        score=round(score, 3),
    )
    return BehaviorCompareResult(
        execution_available=can_run,
        execution_reason=execution_reason,
        tests=calibrated_tests,
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


def _score_case(
    *,
    case: BehaviorTestCase,
    orig_run: JavaSuiteCaseResult,
    gen_run: JavaSuiteCaseResult,
) -> tuple[str, str, bool, bool]:
    """Фактический статус прогона: pass/fail/error/timeout, без invalid_script."""
    orig_ran = _run_completed(orig_run)
    gen_ran = _run_completed(gen_run)

    if case.expects_original_failure or case.purpose == "exploit_error":
        bug_hit = orig_ran and _looks_like_failure(orig_run)
        orig_status = _status_from_run(orig_run, ran=orig_ran, treat_failure_as="fail")
        if bug_hit:
            orig_status = "fail"
        orig_match = bug_hit
        if not gen_ran:
            gen_status = _status_from_run(gen_run, ran=False, treat_failure_as="error")
            gen_match = False
        elif _looks_like_failure(gen_run):
            gen_status = _status_from_run(gen_run, ran=True, treat_failure_as="fail")
            gen_match = False
        else:
            gen_status = "pass"
            gen_match = True
        return orig_status, gen_status, orig_match, gen_match

    # workability: original = baseline; status отражает реальный прогон.
    if not orig_ran:
        orig_status = _status_from_run(orig_run, ran=False, treat_failure_as="error")
        gen_status = _status_from_run(gen_run, ran=gen_ran, treat_failure_as="fail")
        return orig_status, gen_status, False, False

    if _looks_like_failure(orig_run):
        orig_status = _status_from_run(orig_run, ran=True, treat_failure_as="fail")
        # Baseline - факт original (в т.ч. fail). Repaired pass, если завершился иначе
        # (исправление) или совпал по поведению.
        if not gen_ran:
            gen_status = _status_from_run(gen_run, ran=False, treat_failure_as="error")
            gen_match = False
        elif _same_behavior(orig_run, gen_run):
            gen_status = orig_status
            gen_match = True
        elif not _looks_like_failure(gen_run):
            gen_status = "pass"
            gen_match = True
        else:
            gen_status = _status_from_run(gen_run, ran=True, treat_failure_as="fail")
            gen_match = False
        return orig_status, gen_status, True, gen_match

    orig_status = "pass"
    orig_match = True
    if not gen_ran:
        gen_status = _status_from_run(gen_run, ran=False, treat_failure_as="error")
        return orig_status, gen_status, orig_match, False
    gen_match = _same_behavior(orig_run, gen_run)
    gen_status = "pass" if gen_match else _status_from_run(
        gen_run, ran=True, treat_failure_as="fail"
    )
    return orig_status, gen_status, orig_match, gen_match


def _status_from_run(
    run: JavaSuiteCaseResult,
    *,
    ran: bool,
    treat_failure_as: str,
) -> str:
    if run.detail == "case_timeout" or run.exit_code in {124, 137}:
        return "timeout"
    if not ran:
        if run.status in {"error", "fail", "skipped"}:
            return run.status
        return "error"
    if run.exit_code == 0 and not _stderr_has_exception(run):
        return "pass"
    if run.status == "error":
        return "error"
    return treat_failure_as


def _build_run_detail(
    *,
    case: BehaviorTestCase,
    orig_run: JavaSuiteCaseResult,
    gen_run: JavaSuiteCaseResult,
    orig_status: str,
    gen_status: str,
    wall_ratio: float | None,
    cpu_ratio: float | None,
    rss_ratio: float | None,
    resources_vs_baseline: str,
) -> str:
    parts: list[str] = []
    if case.description:
        parts.append(f"desc={case.description}")
    if case.error_description:
        parts.append(f"error={case.error_description}")
    parts.append(f"purpose={case.purpose}")
    if case.related_issue_id:
        parts.append(f"issue={case.related_issue_id}")
    parts.append(
        f"orig={orig_run.detail}/exit={orig_run.exit_code};"
        f"gen={gen_run.detail}/exit={gen_run.exit_code}"
    )
    if orig_status not in {"pass", "skipped"}:
        parts.append("original:" + _stderr_snippet(orig_run))
    if gen_status not in {"pass", "skipped"}:
        parts.append("repaired:" + _stderr_snippet(gen_run))
    ratio_bits = []
    if wall_ratio is not None:
        ratio_bits.append(f"wall_x{wall_ratio:.2f}")
    if cpu_ratio is not None:
        ratio_bits.append(f"cpu_x{cpu_ratio:.2f}")
    if rss_ratio is not None:
        ratio_bits.append(f"rss_x{rss_ratio:.2f}")
    if ratio_bits:
        parts.append(
            f"vs_baseline[{resources_vs_baseline}]:" + ",".join(ratio_bits)
        )
    parts.append(_metrics_brief("o", orig_run.metrics))
    parts.append(_metrics_brief("g", gen_run.metrics))
    return "; ".join(parts)[:2000]


def _stderr_snippet(run: JavaSuiteCaseResult) -> str:
    text = (run.stderr or run.stdout or run.detail or "").strip()
    if not text:
        return f"exit={run.exit_code}"
    one_line = " ".join(text.split())
    return one_line[:280]


def _looks_like_failure(run: JavaSuiteCaseResult) -> bool:
    if run.exit_code is None:
        return True
    if run.exit_code != 0:
        return True
    if run.status in {"fail", "error"}:
        return True
    return _stderr_has_exception(run)


def _stderr_has_exception(run: JavaSuiteCaseResult) -> bool:
    stderr_l = (run.stderr or "").lower()
    markers = (
        "exception in thread",
        "nullpointerexception",
        "\tat ",
        "caused by:",
        "error: ",
    )
    return any(marker in stderr_l for marker in markers)


def _run_completed(run: JavaSuiteCaseResult) -> bool:
    """True, если кейс дошёл до java (не compile/docker/missing)."""
    if run.exit_code is None:
        return False
    if run.detail in {
        "compile_error",
        "missing_case_result",
        "missing_original_result",
        "missing_generated_result",
        "docker_unavailable",
        "container_ttl_exceeded",
    }:
        return False
    return not (
        run.detail.startswith("docker_failed") or run.detail.startswith("os_error")
    )


def _same_behavior(left: JavaSuiteCaseResult, right: JavaSuiteCaseResult) -> bool:
    if left.exit_code != right.exit_code:
        return False
    return _normalize_out(left.stdout) == _normalize_out(right.stdout)


def _normalize_out(text: str) -> str:
    return text.replace("\r\n", "\n").strip()


def _compare_resources(
    orig: JavaCaseResourceMetrics | None,
    gen: JavaCaseResourceMetrics | None,
) -> tuple[float | None, float | None, float | None, str]:
    """Сравнивает ресурсы repaired с ориентиром original."""
    if orig is None or gen is None:
        return None, None, None, "n/a"
    wall_ratio = _safe_ratio(gen.wall_ms, orig.wall_ms)
    orig_cpu = _cpu_total(orig)
    gen_cpu = _cpu_total(gen)
    cpu_ratio = _safe_ratio(gen_cpu, orig_cpu)
    rss_ratio = _safe_ratio(gen.max_rss_kb, orig.max_rss_kb)
    status = "ok"
    if wall_ratio is not None and wall_ratio >= _WALL_SLOW_RATIO:
        status = "slower"
    if rss_ratio is not None and rss_ratio >= _RSS_HEAVY_RATIO:
        status = "heavier" if status == "ok" else f"{status}+heavier"
    if (
        wall_ratio is not None
        and wall_ratio <= 1.15
        and (rss_ratio is None or rss_ratio <= 1.25)
        and (cpu_ratio is None or cpu_ratio <= 1.25)
    ):
        status = "ok"
    return wall_ratio, cpu_ratio, rss_ratio, status


def _cpu_total(metrics: JavaCaseResourceMetrics) -> int | None:
    user = metrics.cpu_user_ms
    sys = metrics.cpu_sys_ms
    if user is None and sys is None:
        return None
    return (user or 0) + (sys or 0)


def _safe_ratio(numerator: int | None, denominator: int | None) -> float | None:
    if numerator is None or denominator is None:
        return None
    if denominator <= 0:
        return None if numerator <= 0 else float(numerator)
    return round(numerator / denominator, 3)


def _m_wall(metrics: JavaCaseResourceMetrics | None) -> int | None:
    return metrics.wall_ms if metrics else None


def _m_cpu_user(metrics: JavaCaseResourceMetrics | None) -> int | None:
    return metrics.cpu_user_ms if metrics else None


def _m_cpu_sys(metrics: JavaCaseResourceMetrics | None) -> int | None:
    return metrics.cpu_sys_ms if metrics else None


def _m_rss(metrics: JavaCaseResourceMetrics | None) -> int | None:
    return metrics.max_rss_kb if metrics else None


def _metrics_brief(prefix: str, metrics: JavaCaseResourceMetrics | None) -> str:
    if metrics is None:
        return f"{prefix}=n/a"
    return (
        f"{prefix}:wall={metrics.wall_ms}ms,"
        f"cpu={metrics.cpu_user_ms}+{metrics.cpu_sys_ms}ms,"
        f"rss={metrics.max_rss_kb}kb"
    )
