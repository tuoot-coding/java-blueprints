from __future__ import annotations

from app.ir.builder import build_structural_ir
from app.llm.logic_outline import build_logic_outline
from app.parser.service import inspect_java_source


def test_logic_outline_captures_control_flow() -> None:
    source = """
class Demo {
  int abs(int n) {
    if (n < 0) {
      return -n;
    }
    return n;
  }

  int sum(int[] a) {
    int s = 0;
    for (int i = 0; i < a.length; i++) {
      s += a[i];
    }
    return s;
  }
}
"""
    inspection = inspect_java_source(source)
    ir = build_structural_ir(source, inspection.tree)
    outline = build_logic_outline(ir)
    assert "abs(" in outline.text
    assert "if (" in outline.text
    assert "for (" in outline.text or "for (" in outline.text.replace("foreach", "for")
    assert outline.method_count == 2
    assert outline.control_nodes >= 2
