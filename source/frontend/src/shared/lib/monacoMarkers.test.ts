import { describe, expect, it } from "vitest";

import { diagnosticsToMonacoMarkers } from "@/shared/lib/monacoMarkers";
import type { SyntaxDiagnostic } from "@/shared/types/parser";

describe("diagnosticsToMonacoMarkers", () => {
  it("сохраняет 1-based UTF-16 координаты", () => {
    const diagnostic: SyntaxDiagnostic = {
      severity: "error",
      code: "java.syntax_error",
      message: "err",
      start_line: 2,
      start_column: 5,
      end_line: 2,
      end_column: 8,
      start_byte: 10,
      end_byte: 13,
    };
    const [marker] = diagnosticsToMonacoMarkers([diagnostic]);
    expect(marker.startLineNumber).toBe(2);
    expect(marker.startColumn).toBe(5);
    expect(marker.endLineNumber).toBe(2);
    expect(marker.endColumn).toBe(8);
    expect(marker.severity).toBe(8);
  });

  it("неизвестный severity даёт Hint, не Error", () => {
    const diagnostic = {
      severity: "info",
      code: "java.syntax_error",
      message: "info",
      start_line: 1,
      start_column: 1,
      end_line: 1,
      end_column: 2,
      start_byte: 0,
      end_byte: 1,
    } as unknown as SyntaxDiagnostic;
    const [marker] = diagnosticsToMonacoMarkers([diagnostic]);
    expect(marker.severity).toBe(2);
  });
});
