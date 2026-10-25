import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useParseJava } from "@/hooks/useParseJava";

describe("useParseJava", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("сохраняет success и очищает устаревший результат при смене исходника", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        headers: new Headers(),
        json: async () => ({
          status: "ok",
          has_syntax_errors: false,
          diagnostics: [],
          root: {
            type: "program",
            start_byte: 0,
            end_byte: 0,
            start_line: 1,
            start_column: 1,
            end_line: 1,
            end_column: 1,
            child_count: 0,
          },
          source_byte_length: 0,
          coordinate_system: "line_utf16_column_1_based_half_open",
          grammar: "tree-sitter-java",
        }),
      }),
    );

    const { result } = renderHook(() => useParseJava());
    await act(async () => {
      await result.current.runParse("class A {}");
    });
    expect(result.current.parseState.kind).toBe("success");

    act(() => {
      result.current.invalidateOnSourceChange("class B {}");
    });
    expect(result.current.parseState.kind).toBe("idle");
  });

  it("переходит в request_error при сетевой ошибке", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const { result } = renderHook(() => useParseJava());
    await act(async () => {
      await result.current.runParse("class A {}");
    });
    expect(result.current.parseState.kind).toBe("request_error");
  });
});
