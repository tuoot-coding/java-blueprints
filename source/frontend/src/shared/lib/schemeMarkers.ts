/** Привязка диагностик к блокам схемы по IR id и перекрытию span. */

import type { SchemeMarker, SchemeSeverity } from "@/shared/lib/schemeTheme";
import type {
  LlmIssue,
  ScratchBlock,
  ScratchProgram,
  StaticDiagnostic,
} from "@/shared/types/workspace";
import type { SyntaxDiagnostic } from "@/shared/types/parser";

export interface SchemeDiagnosticInput {
  syntax?: SyntaxDiagnostic[];
  staticItems?: StaticDiagnostic[];
  llmIssues?: LlmIssue[];
}

function normalizeSeverity(raw: string): SchemeSeverity {
  const value = raw.toLowerCase();
  if (value === "error" || value === "fatal") {
    return "error";
  }
  if (value === "warning" || value === "warn") {
    return "warning";
  }
  return "info";
}

function spansOverlap(
  a: { start_line: number; end_line: number; start_column: number; end_column: number },
  b: { start_line: number; end_line: number; start_column: number; end_column: number },
): boolean {
  if (a.end_line < b.start_line || b.end_line < a.start_line) {
    return false;
  }
  if (a.start_line === b.end_line && a.start_column > b.end_column) {
    return false;
  }
  if (b.start_line === a.end_line && b.start_column > a.end_column) {
    return false;
  }
  return true;
}

function bump(
  map: Map<string, SchemeMarker>,
  blockId: string,
  severity: SchemeSeverity,
): void {
  const current = map.get(blockId);
  if (!current) {
    map.set(blockId, { severity, count: 1 });
    return;
  }
  const rank = { error: 3, warning: 2, info: 1 } as const;
  const nextSeverity = rank[severity] >= rank[current.severity] ? severity : current.severity;
  map.set(blockId, { severity: nextSeverity, count: current.count + 1 });
}

function findBlocksForSpan(
  blocks: ScratchBlock[],
  span: { start_line: number; end_line: number; start_column: number; end_column: number },
): ScratchBlock[] {
  const overlapping = blocks.filter((block) =>
    spansOverlap(
      {
        start_line: block.span.start_line,
        end_line: block.span.end_line,
        start_column: block.span.start_column,
        end_column: block.span.end_column,
      },
      span,
    ),
  );
  if (overlapping.length === 0) {
    return [];
  }
  // Ближайший по размеру span - точнее к узлу условия/операции.
  return [...overlapping].sort(
    (left, right) =>
      left.span.end_byte -
      left.span.start_byte -
      (right.span.end_byte - right.span.start_byte),
  ).slice(0, 1);
}

/** Строит карту blockId -> маркер критичности для отрисовки на схеме. */
export function buildSchemeMarkers(
  scratch: ScratchProgram | null | undefined,
  input: SchemeDiagnosticInput,
): Map<string, SchemeMarker> {
  const result = new Map<string, SchemeMarker>();
  if (!scratch || scratch.blocks.length === 0) {
    return result;
  }
  const byIr = new Map(scratch.blocks.map((block) => [block.ir_node_id, block]));

  for (const item of input.staticItems ?? []) {
    const severity = normalizeSeverity(item.severity);
    let matched = false;
    for (const irId of item.related_ir_ids) {
      const block = byIr.get(irId);
      if (block) {
        bump(result, block.id, severity);
        matched = true;
      }
    }
    if (!matched) {
      for (const block of findBlocksForSpan(scratch.blocks, item.span)) {
        bump(result, block.id, severity);
      }
    }
  }

  for (const item of input.llmIssues ?? []) {
    // На схеме маркеры только для проблем, влияющих на выполнение.
    if (item.affects_execution === false) {
      continue;
    }
    const severity = normalizeSeverity(item.severity);
    for (const block of findBlocksForSpan(scratch.blocks, {
      start_line: item.start_line,
      end_line: item.end_line,
      start_column: item.start_column,
      end_column: item.end_column,
    })) {
      bump(result, block.id, severity);
    }
  }

  for (const item of input.syntax ?? []) {
    if (item.severity !== "error" && item.severity !== "ERROR") {
      continue;
    }
    for (const block of findBlocksForSpan(scratch.blocks, {
      start_line: item.start_line,
      end_line: item.end_line,
      start_column: item.start_column,
      end_column: item.end_column,
    })) {
      bump(result, block.id, "error");
    }
  }

  return result;
}
