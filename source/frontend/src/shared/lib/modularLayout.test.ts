import { describe, expect, it } from "vitest";

import { layoutModularFlow } from "@/shared/lib/modularLayout";
import type { ScratchBlock, ScratchProgram } from "@/shared/types/workspace";

function block(
  id: string,
  kind: string,
  links: ScratchBlock["links"] = [],
  parentId: string | null = null,
): ScratchBlock {
  return {
    id,
    kind,
    label: id,
    ir_node_id: id,
    span: {
      start_byte: 0,
      end_byte: 1,
      start_line: 1,
      start_column: 1,
      end_line: 1,
      end_column: 2,
    },
    parent_id: parentId,
    nest_level: parentId ? 1 : 0,
    color: "#475569",
    links,
    source_snippet: id,
  };
}

describe("layoutModularFlow", () => {
  it("строит top-down поток метода с циклом-контейнером", () => {
    const scratch: ScratchProgram = {
      method_name: "process",
      method_ir_id: "m",
      root_block_ids: ["m"],
      blocks: [
        block("m", "method", [{ kind: "body", target_id: "loop" }]),
        block("loop", "foreach", [
          { kind: "body", target_id: "call" },
          { kind: "next", target_id: "ret" },
        ]),
        block("call", "call", [], "loop"),
        block("ret", "return"),
      ],
    };
    const { nodes, edges } = layoutModularFlow(scratch, null, false, new Map());
    const loop = nodes.find((node) => node.id === "loop");
    const call = nodes.find((node) => node.id === "call");
    const callout = nodes.find((node) => node.id === "callout:call");
    expect(loop?.type).toBe("structureContainer");
    expect(call?.parentId).toBe("loop");
    expect(call?.extent).toBe("parent");
    expect(callout).toBeTruthy();
    expect(callout?.parentId).toBeUndefined();
    expect(edges.some((edge) => edge.type === "schemeCallout")).toBe(true);
    // Выход из цикла - только от контейнера, не от внутреннего call.
    const exitEdge = edges.find((edge) => edge.source === "loop" && edge.target === "ret");
    const bodyEdge = edges.find((edge) => edge.source === "loop" && edge.target === "call");
    expect(exitEdge).toBeTruthy();
    expect((exitEdge?.data as { flowScope?: string } | undefined)?.flowScope).toBe("outer");
    expect((bodyEdge?.data as { flowScope?: string } | undefined)?.flowScope).toBe("inner");
    expect(edges.some((edge) => edge.source === "call" && edge.target === "ret")).toBe(false);
    // Callout в отдельной колонке справа от контейнера, без пересечения с телом.
    expect((callout?.position.x ?? 0) > ((loop?.position.x ?? 0) + Number(loop?.style?.width ?? 0))).toBe(
      true,
    );
  });

  it("не ведёт next из тела цикла на внешний выход контейнера", () => {
    const scratch: ScratchProgram = {
      method_name: "process",
      method_ir_id: "m",
      root_block_ids: ["m"],
      blocks: [
        block("m", "method", [{ kind: "body", target_id: "loop" }]),
        block("loop", "while", [
          { kind: "body", target_id: "op" },
          { kind: "next", target_id: "after" },
        ]),
        block("op", "expression", [{ kind: "next", target_id: "after" }], "loop"),
        block("after", "return"),
      ],
    };
    const { edges } = layoutModularFlow(scratch, null, false);
    expect(edges.some((edge) => edge.source === "op" && edge.target === "after")).toBe(false);
    expect(edges.some((edge) => edge.source === "loop" && edge.target === "after")).toBe(true);
  });

  it("пустой цикл имеет выделенное тело-контейнер", () => {
    const scratch: ScratchProgram = {
      method_name: "process",
      method_ir_id: "m",
      root_block_ids: ["m"],
      blocks: [
        block("m", "method", [{ kind: "body", target_id: "loop" }]),
        block("loop", "foreach"),
      ],
    };
    const { nodes } = layoutModularFlow(scratch, null, true);
    const loop = nodes.find((node) => node.id === "loop");
    expect(loop?.type).toBe("structureContainer");
    expect(Number(loop?.style?.height ?? 0)).toBeGreaterThan(180);
  });

  it("оборачивает try/switch в структурные контейнеры", () => {
    const scratch: ScratchProgram = {
      method_name: "t",
      method_ir_id: "m",
      root_block_ids: ["m"],
      blocks: [
        block("m", "method", [{ kind: "body", target_id: "try1" }]),
        block("try1", "try", [{ kind: "body", target_id: "op" }, { kind: "next", target_id: "sw" }]),
        block("op", "expression"),
        block("sw", "switch", [{ kind: "body", target_id: "case1" }]),
        block("case1", "case", [{ kind: "body", target_id: "ret" }]),
        block("ret", "return"),
      ],
    };
    const { nodes } = layoutModularFlow(scratch, null, false);
    expect(nodes.find((node) => node.id === "try1")?.type).toBe("structureContainer");
    expect(nodes.find((node) => node.id === "sw")?.type).toBe("structureContainer");
    expect(nodes.find((node) => node.id === "case1")?.type).toBe("structureContainer");
    expect(nodes.find((node) => node.id === "op")?.parentId).toBe("try1");
  });

  it("вешает маркеры анализа пунктиром вправо", () => {
    const scratch: ScratchProgram = {
      method_name: "x",
      method_ir_id: "m",
      root_block_ids: ["m"],
      blocks: [
        block("m", "method", [{ kind: "body", target_id: "iff" }]),
        block("iff", "if"),
      ],
    };
    const markers = new Map([["iff", { severity: "error" as const, count: 2 }]]);
    const { nodes, edges } = layoutModularFlow(scratch, null, false, markers);
    expect(nodes.some((node) => node.id === "analysis:iff")).toBe(true);
    expect(edges.some((edge) => edge.type === "schemeAnalysis")).toBe(true);
  });

  it("подписывает Да/Нет на early-exit ветке", () => {
    const scratch: ScratchProgram = {
      method_name: "x",
      method_ir_id: "m",
      root_block_ids: ["m"],
      blocks: [
        block("m", "method", [{ kind: "body", target_id: "iff" }]),
        block("iff", "if", [
          { kind: "body", target_id: "ret" },
          { kind: "next", target_id: "op" },
        ]),
        block("ret", "return"),
        block("op", "expression"),
      ],
    };
    const { edges } = layoutModularFlow(scratch, null, false);
    expect(edges.some((edge) => edge.label === "Да" || edge.label === "Yes")).toBe(true);
    expect(edges.some((edge) => edge.label === "Нет" || edge.label === "No")).toBe(true);
  });
});
