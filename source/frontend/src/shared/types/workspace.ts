/** Типы ответа POST /api/v1/workspace/inspect. */

import type { ParseJavaResponse, SyntaxDiagnostic } from "@/shared/types/parser";

export interface ScratchLink {
  kind: string;
  target_id: string;
}

export interface ScratchBlock {
  id: string;
  kind: string;
  label: string;
  ir_node_id: string;
  span: {
    start_byte: number;
    end_byte: number;
    start_line: number;
    start_column: number;
    end_line: number;
    end_column: number;
  };
  parent_id: string | null;
  nest_level: number;
  color: string;
  links: ScratchLink[];
  source_snippet?: string;
  module_id?: string | null;
  editable?: boolean;
}

export interface ScratchModule {
  id: string;
  kind: string;
  name: string;
  parent_module_id: string | null;
  root_block_id: string;
  block_ids: string[];
}

export interface ScratchProgram {
  method_name: string | null;
  method_ir_id: string | null;
  blocks: ScratchBlock[];
  root_block_ids: string[];
  modules?: ScratchModule[];
  method_names?: string[];
}

export interface LlmSuggestedFix {
  title: string;
  replacement: string;
  start_line: number;
  start_column: number;
  end_line: number;
  end_column: number;
  start_byte: number;
  end_byte: number;
  expected_snippet: string;
  auto_applicable: boolean;
}

export interface LlmIssue {
  id: string;
  severity: "error" | "warning" | "info" | "hint" | string;
  code: string;
  title: string;
  message: string;
  explanation: string;
  start_line: number;
  start_column: number;
  end_line: number;
  end_column: number;
  start_byte: number;
  end_byte: number;
  confidence: string;
  fix: LlmSuggestedFix | null;
  /** false = недочёт структуры, не ломает выполнение программы */
  affects_execution?: boolean;
}

export interface BehaviorTestCase {
  id: string;
  name: string;
  stdin: string;
  expected_stdout: string;
  expected_exit_code: number;
  main_class_hint?: string | null;
}

export interface BehaviorTestRun {
  test_id: string;
  name: string;
  original_status: string;
  generated_status: string;
  original_exit_code: number | null;
  generated_exit_code: number | null;
  original_stdout: string;
  generated_stdout: string;
  expected_stdout: string;
  matched_expected_original: boolean;
  matched_expected_generated: boolean;
  detail: string;
}

export interface BehaviorCompare {
  execution_available: boolean;
  execution_reason: string | null;
  tests: BehaviorTestCase[];
  runs: BehaviorTestRun[];
  original_passed: number;
  generated_passed: number;
  regressions: number;
  improvements: number;
  score: number;
  passed: boolean;
  report_lines: string[];
  notes: string[];
}

export interface LlmLogicalReview {
  status: string;
  issues: LlmIssue[];
  notes: string[];
  model: string | null;
  error_reason: string | null;
}

export interface StaticDiagnostic {
  severity: string;
  rule_id: string;
  message: string;
  explanation: string;
  span: {
    start_line: number;
    start_column: number;
    end_line: number;
    end_column: number;
    start_byte: number;
    end_byte: number;
  };
  related_ir_ids: string[];
  quick_fix_id: string | null;
}

export interface CodeCompareMetrics {
  elapsed_ms: number;
  original_parse_ok: boolean;
  generated_parse_ok: boolean;
  class_names_match: boolean;
  public_methods_preserved: boolean;
  method_count_original: number;
  method_count_generated: number;
  method_count_delta: number;
  line_count_original: number;
  line_count_generated: number;
  line_ratio: number;
  max_method_lines_original: number;
  max_method_lines_generated: number;
  long_method_issues_original: number;
  long_method_issues_generated: number;
  duplicate_logic_original: number;
  duplicate_logic_generated: number;
  max_cyclomatic_original: number;
  max_cyclomatic_generated: number;
  source_changed: boolean;
  unsupported_original: number;
  unsupported_generated: number;
  score: number;
  passed: boolean;
  report_lines: string[];
}

export interface SchemeCompare {
  original_block_count: number;
  generated_block_count: number;
  original_module_count: number;
  generated_module_count: number;
  original_method_names: string[];
  generated_method_names: string[];
  methods_added: string[];
  methods_removed: string[];
  kinds_original: Record<string, number>;
  kinds_generated: Record<string, number>;
  kinds_delta: Record<string, number>;
  structural_similarity: number;
  outline_original: string;
  outline_generated: string;
  changed: boolean;
  report_lines: string[];
}

export interface WorkspaceInspectResponse {
  parse: ParseJavaResponse;
  scratch: ScratchProgram;
  blocks: Array<{ id: string; type: string; label: string; parent_id: string | null }>;
  ir_summary: {
    node_count: number;
    class_names: string[];
    method_names: string[];
    unsupported_count: number;
  };
  static_diagnostics: StaticDiagnostic[];
  quick_fixes: unknown[];
  metrics: unknown;
  llm_configured: boolean;
  logical_review: LlmLogicalReview | null;
  logical_error_count: number;
  source_hash: string;
  coordinate_system: string;
}

export interface ApplyLogicFixResponse {
  source: string;
  source_hash: string;
  previous_source_hash: string;
  issue_id: string;
  has_syntax_errors: boolean;
  parse_diagnostic_count: number;
}

export interface RepairIssueInput {
  id: string;
  severity: string;
  code: string;
  title: string;
  message: string;
  start_line: number;
  end_line: number;
}

export interface RepairWithLlmResponse {
  status: string;
  source: string | null;
  source_hash: string | null;
  previous_source_hash: string;
  fixed_issue_ids: string[];
  notes: string[];
  model: string | null;
  has_syntax_errors: boolean | null;
  parse_diagnostic_count: number | null;
  error_reason: string | null;
  llm_configured: boolean;
  code_compare?: CodeCompareMetrics | null;
  test_compare?: BehaviorCompare | null;
  scheme_compare?: SchemeCompare | null;
  original_scratch?: ScratchProgram | null;
  generated_scratch?: ScratchProgram | null;
}

export interface GenerateFromSchemeResponse {
  status: string;
  source: string | null;
  source_hash: string | null;
  previous_source_hash: string;
  modules_written: string[];
  notes: string[];
  model: string | null;
  has_syntax_errors: boolean | null;
  parse_diagnostic_count: number | null;
  error_reason: string | null;
  llm_configured: boolean;
  code_compare?: CodeCompareMetrics | null;
  test_compare?: BehaviorCompare | null;
  scheme_compare?: SchemeCompare | null;
  scheme_outline?: string | null;
  original_scratch?: ScratchProgram | null;
  generated_scratch?: ScratchProgram | null;
}

export type WorkspaceUiState =
  | { kind: "idle" }
  | { kind: "loading" }
  | {
      kind: "success";
      result: WorkspaceInspectResponse;
      sourceFingerprint: string;
    }
  | {
      kind: "success_with_errors";
      result: WorkspaceInspectResponse;
      sourceFingerprint: string;
    }
  | { kind: "request_error"; message: string; sourceFingerprint: string };

export type UnifiedDiagnostic =
  | { source: "syntax"; item: SyntaxDiagnostic }
  | { source: "static"; item: StaticDiagnostic }
  | { source: "llm"; item: LlmIssue };
