"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";

import { uiText } from "@/shared/i18n/ru";
import type {
  LlmIssue,
  WorkspaceInspectResponse,
  WorkspaceUiState,
} from "@/shared/types/workspace";

export interface RepairIssuePayload {
  id: string;
  severity: string;
  code: string;
  title: string;
  message: string;
  start_line: number;
  end_line: number;
}

interface DiagnosticsPanelProps {
  workspaceState: WorkspaceUiState;
  onReveal: (line: number, column: number) => void;
  onApplyLogicFix?: (issue: LlmIssue) => void;
  onRepairWithLlm?: (issues: RepairIssuePayload[]) => void;
  applyBusyIssueId?: string | null;
  repairBusy?: boolean;
}

interface SelectableIssue {
  key: string;
  severityBucket: "error" | "warning" | "structure";
  severityLabel: string;
  code: string;
  title: string;
  message: string;
  detail?: string;
  line: number;
  column: number;
  endLine: number;
  endColumn: number;
  defaultSelected: boolean;
  llmIssue?: LlmIssue;
  repairPayload: RepairIssuePayload;
}

export function DiagnosticsPanel({
  workspaceState,
  onReveal,
  onApplyLogicFix,
  onRepairWithLlm,
  applyBusyIssueId,
  repairBusy = false,
}: DiagnosticsPanelProps) {
  return (
    <section className="flex h-full min-h-0 flex-col bg-zinc-950">
      <div className="border-b border-zinc-800 px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
        {uiText.diagnosticsTitle}
      </div>
      <div className="flex-1 overflow-auto p-3 text-xs leading-relaxed text-zinc-400">
        {workspaceState.kind === "idle" ? <p>{uiText.diagnosticsIdle}</p> : null}
        {workspaceState.kind === "loading" ? (
          <p className="text-amber-300">{uiText.diagnosticsLoading}</p>
        ) : null}
        {workspaceState.kind === "request_error" ? (
          <p className="text-red-300">
            {uiText.diagnosticsRequestError}: {workspaceState.message}
          </p>
        ) : null}
        {workspaceState.kind === "success" || workspaceState.kind === "success_with_errors" ? (
          <SuccessBody
            result={workspaceState.result}
            onReveal={onReveal}
            onApplyLogicFix={onApplyLogicFix}
            onRepairWithLlm={onRepairWithLlm}
            applyBusyIssueId={applyBusyIssueId}
            repairBusy={repairBusy}
          />
        ) : null}
      </div>
    </section>
  );
}

function SuccessBody({
  result,
  onReveal,
  onApplyLogicFix,
  onRepairWithLlm,
  applyBusyIssueId,
  repairBusy,
}: {
  result: WorkspaceInspectResponse;
  onReveal: (line: number, column: number) => void;
  onApplyLogicFix?: (issue: LlmIssue) => void;
  onRepairWithLlm?: (issues: RepairIssuePayload[]) => void;
  applyBusyIssueId?: string | null;
  repairBusy: boolean;
}) {
  const selectable = useMemo(() => buildSelectableIssues(result), [result]);
  const [selected, setSelected] = useState<Set<string>>(() => defaultSelection(selectable));

  useEffect(() => {
    setSelected(defaultSelection(selectable));
  }, [selectable]);

  const errors = selectable.filter((item) => item.severityBucket === "error");
  const warnings = selectable.filter((item) => item.severityBucket === "warning");
  const structure = selectable.filter((item) => item.severityBucket === "structure");
  const syntax = result.parse.diagnostics;
  const selectedCount = selectable.filter((item) => selected.has(item.key)).length;
  const canRepair =
    Boolean(onRepairWithLlm) &&
    result.llm_configured &&
    !result.parse.has_syntax_errors &&
    selectable.length > 0;

  function toggle(key: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }

  function selectBucket(bucket: SelectableIssue["severityBucket"], on: boolean) {
    setSelected((prev) => {
      const next = new Set(prev);
      for (const item of selectable) {
        if (item.severityBucket !== bucket) {
          continue;
        }
        if (on) {
          next.add(item.key);
        } else {
          next.delete(item.key);
        }
      }
      return next;
    });
  }

  function handleRepairClick() {
    const issues = selectable
      .filter((item) => selected.has(item.key))
      .map((item) => item.repairPayload);
    if (issues.length === 0) {
      return;
    }
    onRepairWithLlm?.(issues);
  }

  return (
    <div className="space-y-4">
      {!result.llm_configured ? (
        <p className="text-[11px] text-zinc-500">{uiText.diagnosticsLlmOff}</p>
      ) : null}
      {result.logical_review && result.logical_review.status !== "ok" ? (
        <div className="space-y-1 text-[11px] text-amber-300">
          <p>
            {uiText.diagnosticsLlmStatus}: {result.logical_review.status}
            {result.logical_review.error_reason
              ? ` (${result.logical_review.error_reason})`
              : ""}
          </p>
          {llmAuthHint(result.logical_review.error_reason) ? (
            <p className="text-amber-200/90">{llmAuthHint(result.logical_review.error_reason)}</p>
          ) : null}
        </div>
      ) : null}

      <p className="text-[11px] text-zinc-300">
        {uiText.diagnosticsLogicalCount}: {errors.length} · {uiText.diagnosticsWarningsCount}:{" "}
        {warnings.length} · {uiText.diagnosticsStructureCount}: {structure.length}
      </p>

      {canRepair ? (
        <div className="space-y-2 rounded border border-zinc-800 bg-zinc-900/40 p-2">
          <p className="text-[10px] text-zinc-500">{uiText.diagnosticsRepairSelectHint}</p>
          <div className="flex flex-wrap gap-2 text-[10px]">
            <button
              type="button"
              className="rounded border border-zinc-700 px-2 py-0.5 text-zinc-200 hover:bg-zinc-800"
              onClick={() => selectBucket("error", true)}
            >
              {uiText.diagnosticsSelectErrors}
            </button>
            <button
              type="button"
              className="rounded border border-zinc-700 px-2 py-0.5 text-zinc-200 hover:bg-zinc-800"
              onClick={() => selectBucket("warning", true)}
            >
              {uiText.diagnosticsSelectWarnings}
            </button>
            <button
              type="button"
              className="rounded border border-zinc-700 px-2 py-0.5 text-zinc-200 hover:bg-zinc-800"
              onClick={() => setSelected(new Set())}
            >
              {uiText.diagnosticsSelectNone}
            </button>
          </div>
          <button
            type="button"
            disabled={repairBusy || applyBusyIssueId != null || selectedCount === 0}
            className="w-full rounded border border-sky-700 bg-sky-950/40 px-2 py-1.5 text-[11px] font-medium text-sky-100 hover:bg-sky-900/50 disabled:opacity-50"
            onClick={handleRepairClick}
          >
            {repairBusy
              ? uiText.diagnosticsRepairLlmBusy
              : `${uiText.diagnosticsRepairLlmSelected} (${selectedCount})`}
          </button>
        </div>
      ) : null}

      {selectable.length + syntax.length === 0 ? (
        <p className="text-emerald-300">{uiText.diagnosticsOk}</p>
      ) : null}

      {syntax.length > 0 ? (
        <Section title={`${uiText.diagnosticsSyntax} (${syntax.length})`}>
          {syntax.map((item, index) => (
            <IssueCard
              key={`syn-${item.code}-${item.start_byte}-${index}`}
              severity={item.severity}
              code={item.code}
              message={item.message}
              line={item.start_line}
              column={item.start_column}
              endLine={item.end_line}
              endColumn={item.end_column}
              onReveal={onReveal}
              tone="error"
            />
          ))}
        </Section>
      ) : null}

      {errors.length > 0 ? (
        <Section title={`${uiText.diagnosticsErrors} (${errors.length})`}>
          {errors.map((item) => (
            <SelectableIssueCard
              key={item.key}
              item={item}
              checked={selected.has(item.key)}
              onToggle={() => toggle(item.key)}
              onReveal={onReveal}
              onApplyLogicFix={onApplyLogicFix}
              applyBusyIssueId={applyBusyIssueId}
              selectable={canRepair}
              tone="error"
            />
          ))}
        </Section>
      ) : null}

      {warnings.length > 0 ? (
        <Section title={`${uiText.diagnosticsWarnings} (${warnings.length})`}>
          {warnings.map((item) => (
            <SelectableIssueCard
              key={item.key}
              item={item}
              checked={selected.has(item.key)}
              onToggle={() => toggle(item.key)}
              onReveal={onReveal}
              onApplyLogicFix={onApplyLogicFix}
              applyBusyIssueId={applyBusyIssueId}
              selectable={canRepair}
              tone="warning"
            />
          ))}
        </Section>
      ) : null}

      {structure.length > 0 ? (
        <Section title={`${uiText.diagnosticsStructure} (${structure.length})`}>
          {structure.map((item) => (
            <SelectableIssueCard
              key={item.key}
              item={item}
              checked={selected.has(item.key)}
              onToggle={() => toggle(item.key)}
              onReveal={onReveal}
              onApplyLogicFix={onApplyLogicFix}
              applyBusyIssueId={applyBusyIssueId}
              selectable={canRepair}
              tone="structure"
            />
          ))}
        </Section>
      ) : null}
    </div>
  );
}

function buildSelectableIssues(result: WorkspaceInspectResponse): SelectableIssue[] {
  const items: SelectableIssue[] = [];
  for (const item of result.logical_review?.issues ?? []) {
    const bucket = severityBucket(item.severity, item.affects_execution);
    items.push({
      key: `llm:${item.id}:${item.code}:${item.start_line}`,
      severityBucket: bucket,
      severityLabel: item.severity,
      code: item.code,
      title: item.title,
      message: item.message,
      detail: item.explanation,
      line: item.start_line,
      column: item.start_column,
      endLine: item.end_line,
      endColumn: item.end_column,
      defaultSelected: bucket === "error",
      llmIssue: item,
      repairPayload: {
        id: item.id,
        severity: item.severity,
        code: item.code,
        title: item.title,
        message: item.message,
        start_line: item.start_line,
        end_line: item.end_line,
      },
    });
  }
  result.static_diagnostics.forEach((item, index) => {
    const id = `static_${item.rule_id}_${index}`;
    const bucket = staticBucket(item.rule_id, item.severity);
    items.push({
      key: `st:${item.rule_id}:${item.span.start_byte}:${index}`,
      severityBucket: bucket,
      severityLabel: bucket,
      code: item.rule_id,
      title: item.rule_id,
      message: item.message,
      detail: item.explanation,
      line: item.span.start_line,
      column: item.span.start_column,
      endLine: item.span.end_line,
      endColumn: item.span.end_column,
      defaultSelected: bucket === "error",
      repairPayload: {
        id,
        severity: bucket,
        code: item.rule_id,
        title: item.rule_id,
        message: item.message,
        start_line: item.span.start_line,
        end_line: item.span.end_line,
      },
    });
  });
  return items;
}

function defaultSelection(items: SelectableIssue[]): Set<string> {
  return new Set(items.filter((item) => item.defaultSelected).map((item) => item.key));
}

function severityBucket(
  severity: string,
  affectsExecution: boolean | undefined,
): "error" | "warning" | "structure" {
  const value = severity.toLowerCase();
  if (value === "error") {
    return "error";
  }
  if (value === "warning") {
    return "warning";
  }
  if (value === "structure" || value === "info" || value === "hint" || affectsExecution === false) {
    return "structure";
  }
  return "warning";
}

function staticBucket(ruleId: string, severity: string): "error" | "warning" | "structure" {
  if (ruleId === "java.unreachable_code" || severity === "error") {
    return "error";
  }
  if (
    ["java.long_method", "java.duplicate_logic", "java.cyclomatic_complexity"].includes(ruleId)
  ) {
    return "structure";
  }
  return "warning";
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="space-y-2">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">{title}</p>
      <ul className="space-y-2">{children}</ul>
    </div>
  );
}

function SelectableIssueCard({
  item,
  checked,
  onToggle,
  onReveal,
  onApplyLogicFix,
  applyBusyIssueId,
  selectable,
  tone,
}: {
  item: SelectableIssue;
  checked: boolean;
  onToggle: () => void;
  onReveal: (line: number, column: number) => void;
  onApplyLogicFix?: (issue: LlmIssue) => void;
  applyBusyIssueId?: string | null;
  selectable: boolean;
  tone: "error" | "warning" | "structure";
}) {
  return (
    <li
      className={`rounded border p-2 ${
        tone === "error"
          ? "border-red-900/50 bg-red-950/20"
          : tone === "warning"
            ? "border-amber-900/50 bg-amber-950/20"
            : "border-sky-900/50 bg-sky-950/20"
      }`}
    >
      <div className="flex items-start gap-2">
        {selectable ? (
          <input
            type="checkbox"
            className="mt-0.5"
            checked={checked}
            onChange={onToggle}
            aria-label={uiText.diagnosticsSelectIssue}
          />
        ) : null}
        <div className="min-w-0 flex-1">
          <div className="font-medium text-zinc-200">
            [{item.severityLabel}] {item.code}
          </div>
          <div className="mt-1 text-zinc-300">
            {item.title}: {item.message}
          </div>
          {item.detail ? <div className="mt-1 text-[11px] text-zinc-500">{item.detail}</div> : null}
          <div className="mt-1 text-[10px] text-zinc-500">
            {item.line}:{item.column} - {item.endLine}:{item.endColumn}
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            <button
              type="button"
              className="rounded border border-zinc-700 px-2 py-0.5 text-[10px] text-zinc-200 hover:bg-zinc-800"
              onClick={() => onReveal(item.line, item.column)}
            >
              {uiText.diagnosticsGoTo}
            </button>
            {item.llmIssue?.fix?.auto_applicable && onApplyLogicFix ? (
              <button
                type="button"
                disabled={applyBusyIssueId === item.llmIssue.id}
                className="rounded border border-emerald-700 px-2 py-0.5 text-[10px] text-emerald-200 hover:bg-emerald-950 disabled:opacity-50"
                onClick={() => onApplyLogicFix(item.llmIssue!)}
              >
                {applyBusyIssueId === item.llmIssue.id
                  ? uiText.diagnosticsFixBusy
                  : uiText.diagnosticsApplyFix}
              </button>
            ) : null}
          </div>
          {item.llmIssue?.fix ? (
            <pre className="mt-2 overflow-auto rounded bg-zinc-950/80 p-2 text-[10px] text-zinc-400">
              {item.llmIssue.fix.title}
              {"\n---\n"}
              {item.llmIssue.fix.expected_snippet}
              {"\n=>\n"}
              {item.llmIssue.fix.replacement}
            </pre>
          ) : null}
        </div>
      </div>
    </li>
  );
}

function IssueCard({
  severity,
  code,
  message,
  detail,
  line,
  column,
  endLine,
  endColumn,
  onReveal,
  tone = "error",
}: {
  severity: string;
  code: string;
  message: string;
  detail?: string;
  line: number;
  column: number;
  endLine: number;
  endColumn: number;
  onReveal: (line: number, column: number) => void;
  tone?: "error" | "warning" | "structure";
}) {
  const borderClass =
    tone === "structure"
      ? "border-sky-900/50 bg-sky-950/20"
      : tone === "warning"
        ? "border-amber-900/50 bg-amber-950/20"
        : "border-red-900/50 bg-red-950/20";
  return (
    <li className={`rounded border p-2 ${borderClass}`}>
      <div className="font-medium text-zinc-200">
        [{severity}] {code}
      </div>
      <div className="mt-1 text-zinc-400">{message}</div>
      {detail ? <div className="mt-1 text-[11px] text-zinc-500">{detail}</div> : null}
      <div className="mt-1 text-[10px] text-zinc-500">
        {line}:{column} - {endLine}:{endColumn}
      </div>
      <button
        type="button"
        className="mt-2 rounded border border-zinc-700 px-2 py-0.5 text-[10px] text-zinc-200 hover:bg-zinc-800"
        onClick={() => onReveal(line, column)}
      >
        {uiText.diagnosticsGoTo}
      </button>
    </li>
  );
}

function llmAuthHint(errorReason: string | null | undefined): string | null {
  if (!errorReason) {
    return null;
  }
  if (errorReason === "oauth_credentials_mismatch" || errorReason === "http_401") {
    return uiText.diagnosticsLlmAuthMismatch;
  }
  if (errorReason === "oauth_authorization_header_invalid") {
    return uiText.diagnosticsLlmAuthInvalid;
  }
  if (errorReason === "oauth_scope_mismatch") {
    return uiText.diagnosticsLlmScopeMismatch;
  }
  return null;
}
