import { afterEach, describe, expect, it, vi } from "vitest";

import { PARSE_PATH, parseJavaSource } from "@/shared/api/parser";

const okBody = {
  status: "ok",
  has_syntax_errors: false,
  diagnostics: [],
  root: {
    type: "program",
    start_byte: 0,
    end_byte: 11,
    start_line: 1,
    start_column: 1,
    end_line: 1,
    end_column: 12,
    child_count: 1,
  },
  source_byte_length: 11,
  coordinate_system: "line_utf16_column_1_based_half_open",
  grammar: "tree-sitter-java",
};

describe("parseJavaSource", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("отправляет source на /api/v1/parser/parse", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers(),
      json: async () => okBody,
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await parseJavaSource("class A {}");
    expect(result.status).toBe("ok");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url.endsWith(PARSE_PATH)).toBe(true);
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({ source: "class A {}" });
  });

  it("пробрасывает сетевую ошибку", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
    );
    await expect(parseJavaSource("class A {}")).rejects.toThrow(/Нет соединения/);
  });
});
