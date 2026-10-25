"use client";

import { uiText } from "@/shared/i18n/ru";
import type { BehaviorCompare } from "@/shared/types/workspace";

interface TestComparePanelProps {
  compare: BehaviorCompare;
  compact?: boolean;
}

/** Результаты 10 LLM-тестов: original vs generated + метрики. */
export function TestComparePanel({ compare, compact = false }: TestComparePanelProps) {
  return (
    <div className={`space-y-2 ${compact ? "p-2" : "p-3"}`}>
      <div className="flex flex-wrap items-center gap-2 text-[11px]">
        <span className="font-semibold uppercase tracking-wide text-zinc-500">
          {uiText.testCompareTitle}
        </span>
        <span className={compare.passed ? "text-emerald-300" : "text-amber-300"}>
          score {compare.score.toFixed(2)} ·{" "}
          {compare.passed ? uiText.testToastPassed : uiText.testToastFailed}
        </span>
        <span className="text-zinc-400">
          {uiText.testComparePass}: {compare.original_passed}→{compare.generated_passed}
        </span>
        <span className="text-zinc-400">
          {uiText.testCompareRegressions}: {compare.regressions} · {uiText.testCompareImprovements}:{" "}
          {compare.improvements}
        </span>
        {compare.execution_available ? (
          <span className="text-zinc-500">{uiText.testCompareIsolated}</span>
        ) : (
          <span className="text-amber-200/90">
            {uiText.testCompareNoExec}
            {compare.execution_reason ? ` (${compare.execution_reason})` : ""}
          </span>
        )}
      </div>

      {compare.runs.length > 0 ? (
        <ul className="max-h-48 space-y-1 overflow-auto text-[10px]">
          {compare.runs.map((run) => (
            <li
              key={run.test_id}
              className="rounded border border-zinc-800 bg-zinc-900/60 px-2 py-1 text-zinc-300"
            >
              <span className="font-medium text-zinc-200">{run.test_id}</span> {run.name}:{" "}
              <span className={statusClass(run.original_status)}>{run.original_status}</span>
              {" → "}
              <span className={statusClass(run.generated_status)}>{run.generated_status}</span>
            </li>
          ))}
        </ul>
      ) : (
        <div className="space-y-1 text-[10px] text-zinc-500">
          <p>{uiText.testCompareEmpty}</p>
          {compare.notes.length > 0 ? (
            <p className="text-amber-200/80">
              {uiText.testCompareNotes}: {compare.notes.slice(0, 4).join("; ")}
            </p>
          ) : null}
        </div>
      )}

      {compare.report_lines.length > 0 ? (
        <pre className="max-h-24 overflow-auto rounded bg-zinc-950/80 p-2 text-[10px] text-zinc-500">
          {compare.report_lines.join("\n")}
        </pre>
      ) : null}
    </div>
  );
}

function statusClass(status: string): string {
  if (status === "pass") {
    return "text-emerald-300";
  }
  if (status === "fail" || status === "error") {
    return "text-red-300";
  }
  return "text-zinc-400";
}
