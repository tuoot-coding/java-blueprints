"""Детерминированная сборка Java из scratch-схемы."""

from __future__ import annotations

from app.ir.builder import build_structural_ir
from app.ir.models import SourceSpan
from app.parser.service import inspect_java_source
from app.structure.scratch import ScratchBlock, ScratchLink, ScratchProgram, build_scratch_program
from app.structure.scratch_codegen import apply_scratch_to_source

SAMPLE = """\
public class A {
  public int f(int x) {
    int y = x + 1;
    if (y > 0) {
      return y;
    }
    return 0;
  }
}
"""


def _program(source: str = SAMPLE) -> ScratchProgram:
    inspection = inspect_java_source(source)
    ir = build_structural_ir(source, inspection.tree)
    return build_scratch_program(ir)


def test_noop_preserves_source_bytes() -> None:
    program = _program()
    assert apply_scratch_to_source(SAMPLE, program) == SAMPLE


def test_insert_user_call_at_method_start() -> None:
    program = _program()
    method = next(block for block in program.blocks if block.kind == "method")
    start = next(
        block for block in program.blocks if block.kind == "start" and block.parent_id == method.id
    )
    first_id = next(link.target_id for link in start.links if link.kind == "next")
    user = ScratchBlock(
        id="user_call_1",
        kind="call",
        label="вызов: doWork()",
        ir_node_id="user_call_1",
        span=SourceSpan(0, 0, 1, 1, 1, 1),
        parent_id=method.id,
        nest_level=2,
        color="#0284c7",
        links=(ScratchLink(kind="next", target_id=first_id),),
        source_snippet="doWork();",
        module_id=method.id,
        editable=True,
    )
    new_blocks: list[ScratchBlock] = []
    for block in program.blocks:
        if block.id == start.id:
            links = [link for link in block.links if link.kind != "next"]
            links.append(ScratchLink(kind="next", target_id=user.id))
            new_blocks.append(
                ScratchBlock(
                    id=block.id,
                    kind=block.kind,
                    label=block.label,
                    ir_node_id=block.ir_node_id,
                    span=block.span,
                    parent_id=block.parent_id,
                    nest_level=block.nest_level,
                    color=block.color,
                    links=tuple(links),
                    source_snippet=block.source_snippet,
                    module_id=block.module_id,
                    editable=block.editable,
                )
            )
        else:
            new_blocks.append(block)
    new_blocks.append(user)
    edited = ScratchProgram(
        method_name=program.method_name,
        method_ir_id=program.method_ir_id,
        blocks=tuple(new_blocks),
        root_block_ids=program.root_block_ids,
        modules=program.modules,
        method_names=program.method_names,
    )
    out = apply_scratch_to_source(SAMPLE, edited)
    assert "doWork();" in out
    assert "int y = x + 1;" in out
    assert out.index("doWork();") < out.index("int y = x + 1;")
