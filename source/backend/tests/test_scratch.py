from __future__ import annotations

from app.ir.builder import build_structural_ir
from app.parser.service import inspect_java_source
from app.structure.scheme_compare import compare_scratch_programs
from app.structure.scratch import build_scratch_program, serialize_scratch_outline


def test_scratch_reflects_if_and_return() -> None:
    source = """
class Demo {
  int abs(int n) {
    if (n < 0) {
      return -n;
    }
    return n;
  }
}
"""
    inspection = inspect_java_source(source)
    ir = build_structural_ir(source, inspection.tree)
    program = build_scratch_program(ir)
    assert program.method_name == "abs"
    kinds = [block.kind for block in program.blocks]
    assert "method" in kinds
    assert "if" in kinds
    assert "return" in kinds
    assert "start" in kinds
    assert "end" in kinds
    assert "class" in kinds
    method = next(block for block in program.blocks if block.kind == "method")
    assert any(link.kind == "body" for link in method.links)
    assert len(program.modules) >= 2
    assert "abs" in program.method_names


def test_scratch_includes_all_methods_as_modules() -> None:
    source = """
class Twin {
  int left(int n) { return n; }
  int right(int n) { return -n; }
}
"""
    inspection = inspect_java_source(source)
    ir = build_structural_ir(source, inspection.tree)
    program = build_scratch_program(ir)
    assert set(program.method_names) == {"left", "right"}
    method_modules = [m for m in program.modules if m.kind == "method"]
    assert len(method_modules) == 2
    outline = serialize_scratch_outline(program)
    assert "left" in outline and "right" in outline


def test_scheme_compare_detects_decomposition() -> None:
    original_src = """
class A {
  int heavy(int n) {
    int s = 0;
    for (int i = 0; i < n; i++) { s += i; }
    return s;
  }
}
"""
    generated_src = """
class A {
  int heavy(int n) { return part(n); }
  private int part(int n) {
    int s = 0;
    for (int i = 0; i < n; i++) { s += i; }
    return s;
  }
}
"""
    orig = build_scratch_program(
        build_structural_ir(original_src, inspect_java_source(original_src).tree)
    )
    gen = build_scratch_program(
        build_structural_ir(generated_src, inspect_java_source(generated_src).tree)
    )
    cmp = compare_scratch_programs(orig, gen)
    assert cmp.changed is True
    assert "part" in cmp.methods_added
    assert cmp.structural_similarity > 0
    assert cmp.generated_module_count >= cmp.original_module_count
