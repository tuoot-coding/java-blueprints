"use client";

import { uiText } from "@/shared/i18n/ru";
import type { BehaviorCompare, CodeCompareMetrics } from "@/shared/types/workspace";

export interface CompareToastState {
  codeCompare: CodeCompareMetrics;
  testCompare?: BehaviorCompare | null;
}

interface CompareResultsToastProps {
  state: CompareToastState | null;
  onClose: () => void;
}

export function CompareResultsToast({ state, onClose }: CompareResultsToastProps) {
  if (!state) {
    return null;
  }
  const { codeCompare, testCompare } = state;
  const passed = testCompare?.passed ?? codeCompare.passed;
  const score = testCompare?.score ?? codeCompare.score;
  return (
    <div
      className="fixed bottom-4 right-4 z-50 w-[min(420px,calc(100vw-2rem))] rounded-lg border border-zinc-700 bg-zinc-950/95 p-3 shadow-2xl shadow-black/50 backdrop-blur"
      role="status"
    >
      <div className="mb-2 flex items-start justify-between gap-2">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400">
            {uiText.testToastTitle}
          </div>
          <div
            className={`mt-0.5 text-sm font-semibold ${
              passed ? "text-emerald-300" : "text-amber-300"
            }`}
          >
            {passed ? uiText.testToastPassed : uiText.testToastFailed}
            {" · "}
            {uiText.testToastScore} {score.toFixed(2)}
          </div>
        </div>
        <button
          type="button"
          className="rounded border border-zinc-700 px-2 py-0.5 text-[10px] text-zinc-300 hover:bg-zinc-800"
          onClick={onClose}
        >
          {uiText.testToastClose}
        </button>
      </div>

      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px] text-zinc-300">
        {testCompare ? (
          <>
            <Metric
              label={uiText.testComparePass}
              value={`${testCompare.original_passed} → ${testCompare.generated_passed}`}
            />
            <Metric label={uiText.testCompareRegressions} value={String(testCompare.regressions)} />
            <Metric
              label={uiText.testCompareImprovements}
              value={String(testCompare.improvements)}
            />
            <Metric
              label={uiText.testCompareTitle}
              value={`${testCompare.tests.length} сценариев`}
            />
          </>
        ) : null}
        <Metric
          label={uiText.testToastMethods}
          value={`${codeCompare.method_count_original} → ${codeCompare.method_count_generated}`}
        />
        <Metric
          label={uiText.compareLines}
          value={`${codeCompare.line_count_original} → ${codeCompare.line_count_generated}`}
        />
      </dl>

      <ul className="mt-2 max-h-24 overflow-auto space-y-0.5 text-[10px] text-zinc-500">
        {(testCompare?.report_lines ?? codeCompare.report_lines).slice(0, 6).map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-2 border-b border-zinc-900 py-0.5">
      <dt className="text-zinc-500">{label}</dt>
      <dd className="font-mono text-zinc-200">{value}</dd>
    </div>
  );
}
