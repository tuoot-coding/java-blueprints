"use client";

import { TestComparePanel } from "@/components/compare/TestComparePanel";
import { uiText } from "@/shared/i18n/ru";
import type {
  BehaviorCompare,
  CodeCompareMetrics,
  ScratchProgram,
} from "@/shared/types/workspace";

export interface RepairCompareState {
  originalSource: string;
  repairedSource: string;
  fixedIssueIds: string[];
  notes: string[];
  testCompare?: BehaviorCompare | null;
  codeCompare?: CodeCompareMetrics | null;
  originalScratch?: ScratchProgram | null;
  generatedScratch?: ScratchProgram | null;
}

interface CodeComparePanelProps {
  compare: RepairCompareState;
  busy: boolean;
  onAccept: () => void;
  onDiscard: () => void;
  onDownloadRepaired: () => void;
  collapsed?: boolean;
  onToggleCollapsed?: () => void;
}

export function CodeComparePanel({
  compare,
  busy,
  onAccept,
  onDiscard,
  onDownloadRepaired,
  collapsed = false,
  onToggleCollapsed,
}: CodeComparePanelProps) {
  const originalLines = compare.originalSource.split("\n").length;
  const repairedLines = compare.repairedSource.split("\n").length;
  const delta = repairedLines - originalLines;
  const metrics = compare.codeCompare;
  const tests = compare.testCompare;

  return (
    <section className="flex min-h-0 flex-1 flex-col overflow-hidden border-b border-zinc-800 bg-zinc-950">
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-zinc-800 px-3 py-1.5">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
          {uiText.compareTitle}
        </span>
        <div className="flex flex-wrap items-center gap-2 text-[10px] text-zinc-500">
          <span>
            {uiText.compareLines}: {originalLines} → {repairedLines} ({delta >= 0 ? "+" : ""}
            {delta})
          </span>
          <span>
            {uiText.compareFixed}: {compare.fixedIssueIds.length}
          </span>
          {tests ? (
            <span className={tests.passed ? "text-emerald-300" : "text-amber-300"}>
              {uiText.testCompareTitle}: {tests.generated_passed}/{tests.tests.length || 10} · score{" "}
              {tests.score.toFixed(2)}
            </span>
          ) : metrics ? (
            <span className={metrics.passed ? "text-emerald-300" : "text-amber-300"}>
              {uiText.testResultsTitle}: score {metrics.score.toFixed(2)}
            </span>
          ) : null}
          <button
            type="button"
            disabled={busy}
            className="rounded border border-emerald-700 bg-emerald-950/40 px-2 py-0.5 text-[10px] font-semibold text-emerald-100 hover:bg-emerald-900/50 disabled:opacity-50"
            onClick={onAccept}
          >
            {uiText.compareAccept}
          </button>
          <button
            type="button"
            disabled={busy}
            className="rounded border border-zinc-700 px-2 py-0.5 text-[10px] font-semibold text-zinc-200 hover:bg-zinc-800 disabled:opacity-50"
            onClick={onDiscard}
          >
            {uiText.compareDiscard}
          </button>
          <button
            type="button"
            disabled={busy}
            className="rounded border border-sky-800 px-2 py-0.5 text-[10px] font-semibold text-sky-100 hover:bg-sky-950/40 disabled:opacity-50"
            onClick={onDownloadRepaired}
          >
            {uiText.compareDownload}
          </button>
          {onToggleCollapsed ? (
            <button
              type="button"
              title={collapsed ? uiText.compareExpand : uiText.compareCollapse}
              aria-label={collapsed ? uiText.compareExpand : uiText.compareCollapse}
              className="rounded border border-zinc-700 px-2 py-0.5 text-[10px] font-semibold leading-none text-zinc-200 hover:bg-zinc-800"
              onClick={onToggleCollapsed}
            >
              {collapsed ? uiText.expandToggle : uiText.collapseToggle}
            </button>
          ) : null}
        </div>
      </div>

      {collapsed ? null : (
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          {compare.notes.length > 0 ? (
            <div className="shrink-0 border-b border-zinc-800 px-3 py-1.5 text-[11px] text-zinc-400">
              {compare.notes.join(" · ")}
            </div>
          ) : null}

          {tests ? (
            <div className="shrink-0 border-b border-zinc-800">
              <TestComparePanel compare={tests} compact />
            </div>
          ) : metrics ? (
            <div className="shrink-0 border-b border-zinc-800 px-3 py-1.5 text-[10px] text-zinc-400">
              {uiText.testToastMethods}: {metrics.method_count_original}→
              {metrics.method_count_generated}
              {" · "}
              {uiText.testToastLong}: {metrics.long_method_issues_original}→
              {metrics.long_method_issues_generated}
              {" · "}
              {uiText.testToastDup}: {metrics.duplicate_logic_original}→
              {metrics.duplicate_logic_generated}
            </div>
          ) : null}

          <div className="grid min-h-0 flex-1 grid-cols-2 gap-px overflow-hidden bg-zinc-800">
            <ComparePane title={uiText.compareOriginal} source={compare.originalSource} />
            <ComparePane title={uiText.compareRepaired} source={compare.repairedSource} />
          </div>
        </div>
      )}
    </section>
  );
}

function ComparePane({ title, source }: { title: string; source: string }) {
  return (
    <div className="flex min-h-0 flex-col overflow-hidden bg-zinc-950">
      <div className="shrink-0 border-b border-zinc-800 px-2 py-1 text-[10px] uppercase tracking-wide text-zinc-500">
        {title}
      </div>
      <pre className="min-h-0 flex-1 overflow-auto p-2 font-mono text-[11px] leading-relaxed text-zinc-300 whitespace-pre">
        {source}
      </pre>
    </div>
  );
}
