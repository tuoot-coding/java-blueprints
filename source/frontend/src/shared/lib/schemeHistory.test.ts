import { describe, expect, it } from "vitest";

import { createBlankScratchProgram, insertBlock } from "@/shared/lib/schemeEdit";
import {
  canUndoScheme,
  createSchemeHistory,
  pushSchemeHistory,
  undoSchemeHistory,
} from "@/shared/lib/schemeHistory";

describe("schemeHistory", () => {
  it("поддерживает undo после нескольких правок", () => {
    const blank = createBlankScratchProgram("process");
    let history = createSchemeHistory(blank);
    const first = insertBlock(blank, "if", { free: true });
    history = pushSchemeHistory(history, first);
    const second = insertBlock(first, "while", { free: true });
    history = pushSchemeHistory(history, second);
    expect(canUndoScheme(history)).toBe(true);
    const once = undoSchemeHistory(history);
    expect(once.program?.blocks).toHaveLength(first.blocks.length);
    const twice = undoSchemeHistory(once.state);
    expect(twice.program?.blocks).toHaveLength(blank.blocks.length);
    expect(canUndoScheme(twice.state)).toBe(false);
  });
});
