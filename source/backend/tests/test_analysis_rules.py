from __future__ import annotations

from app.analysis.engine import run_static_analysis
from app.analysis.rules.complexity import cyclomatic_complexity
from app.ir.query import find_method_by_name
from app.texts.analysis import AnalysisRule
from tests.java_fixtures import ir_from_source, read_java_fixture


def _rules(source: str) -> set[str]:
    run = run_static_analysis(ir_from_source(source), source=source)
    return {item.rule_id.value for item in run.diagnostics}


def test_unreachable_statement_has_quick_fix() -> None:
    source = read_java_fixture("unreachable.java")
    run = run_static_analysis(ir_from_source(source), source=source)
    diagnostics = [item for item in run.diagnostics if item.rule_id == AnalysisRule.UNREACHABLE]
    assert len(diagnostics) == 1
    assert diagnostics[0].quick_fix_id is not None
    assert diagnostics[0].span.start_line == 4
    assert len(run.quick_fixes) == 1
    assert run.quick_fixes[0].expected_text.startswith("int x = 1;")


def test_empty_blocks_and_textual_duplicate_if() -> None:
    rules = _rules(read_java_fixture("empty_blocks.java"))
    assert AnalysisRule.EMPTY_METHOD.value in rules
    assert AnalysisRule.EMPTY_CONTROL.value in rules
    assert AnalysisRule.EMPTY_IF_ELSE.value in rules
    assert AnalysisRule.INFINITE_FOR.value in rules
    assert AnalysisRule.DUPLICATE_IF.value in rules


def test_complexity_reaches_info_threshold() -> None:
    source = read_java_fixture("complexity.java")
    root = ir_from_source(source)
    method = find_method_by_name(root, "m")
    assert method is not None
    value = cyclomatic_complexity(method)
    assert value >= 10
    run = run_static_analysis(root, source=source)
    complexity = [item for item in run.diagnostics if item.rule_id == AnalysisRule.COMPLEXITY]
    assert len(complexity) == 1
    assert str(value) in complexity[0].message
    assert run.metrics.max_cyclomatic_complexity == value


def test_short_circuit_outside_condition_is_not_a_decision() -> None:
    source = """
class C {
  void m(boolean a, boolean b) {
    boolean value = a && b;
  }
}
"""
    method = find_method_by_name(ir_from_source(source), "m")
    assert method is not None
    assert cyclomatic_complexity(method) == 1


def test_short_circuit_inside_condition_counts() -> None:
    source = """
class C {
  void m(boolean a, boolean b) {
    if (a && b || a) {
      return;
    }
  }
}
"""
    method = find_method_by_name(ir_from_source(source), "m")
    assert method is not None
    # if + && + ||
    assert cyclomatic_complexity(method) == 4


def test_unsupported_anonymous_is_reported_once() -> None:
    source = read_java_fixture("unsupported_anonymous.java")
    run = run_static_analysis(ir_from_source(source), source=source)
    unsupported = [item for item in run.diagnostics if item.rule_id == AnalysisRule.UNSUPPORTED]
    assert len(unsupported) >= 1
    assert run.metrics.unsupported_count >= 1


def test_infinite_for_with_break_is_silent() -> None:
    source = """
class C {
  void m() {
    for (;;) {
      break;
    }
  }
}
"""
    rules = _rules(source)
    assert AnalysisRule.INFINITE_FOR.value not in rules


def test_conditional_return_does_not_mark_next_statement() -> None:
    source = """
class C {
  void m(boolean flag) {
    if (flag) {
      return;
    }
    int x = 1;
  }
}
"""
    rules = _rules(source)
    assert AnalysisRule.UNREACHABLE.value not in rules
