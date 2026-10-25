from __future__ import annotations

from app.ir.builder import build_structural_ir
from app.llm.source_pack import FULL_SOURCE_CHAR_LIMIT, build_llm_source_pack
from app.parser.service import inspect_java_source


def test_small_source_includes_logic_outline_and_full_code() -> None:
    source = "class A { int m() { return 1; } }"
    inspection = inspect_java_source(source)
    ir = build_structural_ir(source, inspection.tree)
    pack = build_llm_source_pack(source, ir)
    assert pack.mode == "logic_plus_full"
    assert pack.truncated is False
    assert "LOGIC_OUTLINE:" in pack.payload_text
    assert "SOURCE_FULL:" in pack.payload_text
    assert "m(" in pack.logic_outline
    assert source in pack.payload_text


def test_large_source_is_truncated_with_hotspots() -> None:
    methods = []
    for index in range(30):
        methods.append(
            f"""
  int m{index}(int n) {{
    int s = 0;
    for (int i = 0; i < n; i++) {{
      for (int j = 0; j < n; j++) {{
        s += i + j + {index};
      }}
    }}
    return s;
  }}
"""
        )
    source = "class Big {\n" + "\n".join(methods) + "\n}\n"
    while len(source) <= FULL_SOURCE_CHAR_LIMIT:
        source += "\n// pad " + ("x" * 200)
    inspection = inspect_java_source(source)
    ir = build_structural_ir(source, inspection.tree)
    pack = build_llm_source_pack(source, ir)
    assert pack.truncated is True
    assert pack.mode == "logic_plus_hotspots"
    assert pack.payload_chars < pack.original_chars
    assert len(pack.included_methods) > 0
    assert "LOGIC_OUTLINE:" in pack.payload_text
    assert pack.control_nodes >= 1
