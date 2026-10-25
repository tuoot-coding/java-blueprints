/** Типы Parser API по contracts/openapi.json. */

export type ParseStatus = "ok" | "syntax_errors";

export type DiagnosticSeverity = "error";

export type DiagnosticCode = "java.syntax_error" | "java.missing_node";

export type CoordinateSystem = "line_utf16_column_1_based_half_open";

export interface SyntaxDiagnostic {
  severity: DiagnosticSeverity;
  code: DiagnosticCode;
  message: string;
  start_line: number;
  start_column: number;
  end_line: number;
  end_column: number;
  start_byte: number;
  end_byte: number;
}

export interface SyntaxRootSummary {
  type: string;
  start_byte: number;
  end_byte: number;
  start_line: number;
  start_column: number;
  end_line: number;
  end_column: number;
  child_count: number;
}

export interface ParseJavaResponse {
  status: ParseStatus;
  has_syntax_errors: boolean;
  diagnostics: SyntaxDiagnostic[];
  root: SyntaxRootSummary;
  source_byte_length: number;
  coordinate_system: CoordinateSystem;
  grammar: string;
}

export type ParseUiState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "success"; result: ParseJavaResponse; sourceFingerprint: string }
  | { kind: "success_with_errors"; result: ParseJavaResponse; sourceFingerprint: string }
  | { kind: "request_error"; message: string; sourceFingerprint: string };
