from __future__ import annotations

from app.analysis.rules.bloat import find_bloat
from app.ir.builder import build_structural_ir
from app.parser.service import inspect_java_source
from app.texts.analysis import AnalysisRule


def _ir(source: str):
    inspection = inspect_java_source(source)
    return build_structural_ir(source, inspection.tree)


def test_long_method_detected() -> None:
    body_lines = "\n".join(f"    s += {i};" for i in range(50))
    source = f"""
class Demo {{
  int heavy(int n) {{
    int s = 0;
{body_lines}
    return s;
  }}
}}
"""
    issues = find_bloat(_ir(source))
    assert any(item.rule_id == AnalysisRule.LONG_METHOD for item in issues)


def test_duplicate_logic_detected() -> None:
    source = """
class Demo {
  int a(int n) {
    int s = 0;
    for (int i = 0; i < n; i++) {
      s += i;
      if (i % 2 == 0) { s += 1; }
    }
    return s;
  }
  int b(int n) {
    int s = 0;
    for (int i = 0; i < n; i++) {
      s += i;
      if (i % 2 == 0) { s += 1; }
    }
    return s;
  }
}
"""
    issues = find_bloat(_ir(source))
    assert any(item.rule_id == AnalysisRule.DUPLICATE_LOGIC for item in issues)
