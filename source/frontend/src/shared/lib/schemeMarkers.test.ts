import { describe, expect, it } from "vitest";

import { buildSchemeMarkers } from "@/shared/lib/schemeMarkers";
import type { ScratchBlock, ScratchProgram } from "@/shared/types/workspace";

function block(partial: Partial<ScratchBlock> & Pick<ScratchBlock, "id">): ScratchBlock {
  return {
    id: partial.id,
    kind: partial.kind ?? "if",
    label: partial.label ?? partial.id,
    ir_node_id: partial.ir_node_id ?? partial.id,
    span: partial.span ?? {
      start_byte: 0,
      end_byte: 10,
      start_line: 3,
      start_column: 1,
      end_line: 3,
      end_column: 20,
    },
    parent_id: partial.parent_id ?? null,
    nest_level: partial.nest_level ?? 0,
    color: "#ca8a04",
    links: partial.links ?? [],
  };
}

function program(blocks: ScratchBlock[]): ScratchProgram {
  return {
    method_name: "demo",
    method_ir_id: "m1",
    blocks,
    root_block_ids: blocks[0] ? [blocks[0].id] : [],
  };
}

describe("buildSchemeMarkers", () => {
  it("привязывает static diagnostic по related_ir_ids", () => {
    const scratch = program([block({ id: "n1", ir_node_id: "ir-1" })]);
    const markers = buildSchemeMarkers(scratch, {
      staticItems: [
        {
          severity: "error",
          rule_id: "java.unreachable_code",
          message: "unreachable",
          explanation: "",
          span: {
            start_line: 3,
            start_column: 1,
            end_line: 3,
            end_column: 20,
            start_byte: 0,
            end_byte: 10,
          },
          related_ir_ids: ["ir-1"],
          quick_fix_id: null,
        },
      ],
    });
    expect(markers.get("n1")?.severity).toBe("error");
    expect(markers.get("n1")?.count).toBe(1);
  });

  it("игнорирует LLM-проблемы без влияния на выполнение", () => {
    const scratch = program([block({ id: "n1" })]);
    const markers = buildSchemeMarkers(scratch, {
      llmIssues: [
        {
          id: "i1",
          severity: "warning",
          code: "style",
          title: "style",
          message: "rename",
          explanation: "",
          start_line: 3,
          start_column: 1,
          end_line: 3,
          end_column: 20,
          start_byte: 0,
          end_byte: 10,
          confidence: "medium",
          fix: null,
          affects_execution: false,
        },
      ],
    });
    expect(markers.size).toBe(0);
  });
});
