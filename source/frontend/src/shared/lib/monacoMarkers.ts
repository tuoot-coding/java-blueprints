import type { SyntaxDiagnostic } from "@/shared/types/parser";

export interface MonacoMarkerLike {
  severity: number;
  message: string;
  startLineNumber: number;
  startColumn: number;
  endLineNumber: number;
  endColumn: number;
}

/** MarkerSeverity: Error=8, Warning=4, Info=2, Hint=1 */
function monacoSeverity(severity: string): number {
  const normalized = severity.toLowerCase();
  if (normalized === "error") {
    return 8;
  }
  if (normalized === "warning") {
    return 4;
  }
  if (normalized === "info") {
    return 2;
  }
  return 1;
}

/** Преобразует diagnostics API (1-based, UTF-16, half-open end) в Monaco markers. */
export function diagnosticsToMonacoMarkers(
  diagnostics: SyntaxDiagnostic[],
): MonacoMarkerLike[] {
  return diagnostics.map((item) => ({
    severity: monacoSeverity(item.severity),
    message: `${item.code}: ${item.message}`,
    startLineNumber: item.start_line,
    startColumn: item.start_column,
    endLineNumber: item.end_line,
    endColumn: Math.max(item.end_column, item.start_column + 1),
  }));
}

export const PARSER_MARKER_OWNER = "java-blueprints-parser";
