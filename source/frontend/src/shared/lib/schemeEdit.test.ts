import { describe, expect, it } from "vitest";

import {
  canConnectBlocks,
  canDeleteBlock,
  connectBlocks,
  createBlankScratchProgram,
  deleteBlock,
  disconnectBlocks,
  insertBlock,
  moveBlockAmongSiblings,
  orderedSiblings,
} from "@/shared/lib/schemeEdit";
import type { ScratchBlock, ScratchProgram } from "@/shared/types/workspace";

function block(
  id: string,
  parentId: string | null,
  links: ScratchBlock["links"] = [],
): ScratchBlock {
  return {
    id,
    kind: "expression",
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
    editable: true,
  };
}

function program(blocks: ScratchBlock[]): ScratchProgram {
  return {
    method_name: "m",
    method_ir_id: "m1",
    blocks,
    root_block_ids: ["m1"],
    modules: [],
    method_names: ["m"],
  };
}

describe("schemeEdit", () => {
  it("connectBlocks replaces next link", () => {
    const source = program([
      block("a", "m1", [{ kind: "next", target_id: "b" }]),
      block("b", "m1"),
      block("c", "m1"),
    ]);
    const next = connectBlocks(source, "a", "c", "next");
    const a = next.blocks.find((item) => item.id === "a")!;
    expect(a.links.filter((link) => link.kind === "next")).toEqual([
      { kind: "next", target_id: "c" },
    ]);
  });

  it("disconnectBlocks removes order link", () => {
    const source = program([
      block("a", "m1", [{ kind: "next", target_id: "b" }]),
      block("b", "m1"),
    ]);
    const next = disconnectBlocks(source, "a", "b", "next");
    const a = next.blocks.find((item) => item.id === "a")!;
    expect(a.links).toEqual([]);
  });

  it("moveBlockAmongSiblings swaps next chain order", () => {
    const source = program([
      {
        ...block("m1", null, [{ kind: "body", target_id: "a" }]),
        kind: "method",
        editable: false,
      },
      block("a", "m1", [{ kind: "next", target_id: "b" }]),
      block("b", "m1", [{ kind: "next", target_id: "c" }]),
      block("c", "m1"),
    ]);
    expect(orderedSiblings(source, "m1").map((item) => item.id)).toEqual(["a", "b", "c"]);
    const moved = moveBlockAmongSiblings(source, "b", "up");
    expect(orderedSiblings(moved, "m1").map((item) => item.id)).toEqual(["b", "a", "c"]);
    const parent = moved.blocks.find((item) => item.id === "m1")!;
    expect(parent.links.some((link) => link.kind === "body" && link.target_id === "b")).toBe(
      true,
    );
  });

  it("deleteBlock rewires next chain", () => {
    const source = program([
      {
        ...block("m1", null, [{ kind: "body", target_id: "a" }]),
        kind: "method",
        editable: false,
      },
      block("a", "m1", [{ kind: "next", target_id: "b" }]),
      block("b", "m1", [{ kind: "next", target_id: "c" }]),
      block("c", "m1"),
    ]);
    expect(canDeleteBlock(source, "b")).toBe(true);
    expect(canDeleteBlock(source, "m1")).toBe(false);
    const next = deleteBlock(source, "b");
    expect(next.blocks.map((item) => item.id)).toEqual(["m1", "a", "c"]);
    const a = next.blocks.find((item) => item.id === "a")!;
    expect(a.links.some((link) => link.kind === "next" && link.target_id === "c")).toBe(true);
  });

  it("insertBlock after sibling updates body of parent", () => {
    const source = program([
      {
        ...block("m1", null, [{ kind: "body", target_id: "a" }]),
        kind: "method",
        editable: false,
      },
      block("a", "m1"),
    ]);
    const next = insertBlock(source, "return", { afterId: "a" });
    const siblings = orderedSiblings(next, "m1");
    expect(siblings).toHaveLength(2);
    expect(siblings[0]!.id).toBe("a");
    expect(siblings[1]!.kind).toBe("return");
    expect(siblings[1]!.source_snippet).toContain("return");
  });

  it("insertBlock free не создаёт автосвязи и не зависит от выбора", () => {
    const source = program([
      {
        ...block("m1", null, [{ kind: "body", target_id: "a" }]),
        kind: "method",
        editable: false,
      },
      block("a", "m1"),
    ]);
    const next = insertBlock(source, "if", { free: true, afterId: "a" });
    const added = next.blocks.find((item) => item.kind === "if");
    expect(added).toBeTruthy();
    expect(added!.links).toEqual([]);
    expect(added!.parent_id).toBe("m1");
    const a = next.blocks.find((item) => item.id === "a")!;
    expect(a.links).toEqual([]);
  });

  it("createBlankScratchProgram даёт метод-корень", () => {
    const blank = createBlankScratchProgram("process");
    expect(blank.blocks).toHaveLength(1);
    expect(blank.blocks[0]!.kind).toBe("method");
    expect(blank.root_block_ids).toEqual([blank.blocks[0]!.id]);
  });

  it("connectBlocks body помещает цель внутрь контейнера", () => {
    const source = program([
      {
        ...block("m1", null, []),
        kind: "method",
        editable: false,
      },
      { ...block("loop", "m1"), kind: "foreach" },
      block("op", "m1"),
    ]);
    const next = connectBlocks(source, "loop", "op", "body");
    const loop = next.blocks.find((item) => item.id === "loop")!;
    const op = next.blocks.find((item) => item.id === "op")!;
    expect(loop.links.some((link) => link.kind === "body" && link.target_id === "op")).toBe(true);
    expect(op.parent_id).toBe("loop");
  });

  it("canConnectBlocks запрещает next из тела цикла наружу", () => {
    const source = program([
      {
        ...block("m1", null, [{ kind: "body", target_id: "loop" }]),
        kind: "method",
        editable: false,
      },
      {
        ...block("loop", "m1", [
          { kind: "body", target_id: "op" },
          { kind: "next", target_id: "after" },
        ]),
        kind: "while",
      },
      block("op", "loop"),
      block("after", "m1"),
    ]);
    expect(canConnectBlocks(source, "op", "after", "next")).toBe(false);
    expect(canConnectBlocks(source, "loop", "after", "next")).toBe(true);
    expect(canConnectBlocks(source, "loop", "op", "body")).toBe(true);
  });
});
