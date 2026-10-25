"use client";

import { uiText } from "@/shared/i18n/ru";
import type { BehaviorCompare, BehaviorTestRun } from "@/shared/types/workspace";

interface TestComparePanelProps {
  compare: BehaviorCompare;
  compact?: boolean;
}

/** Результаты 10 LLM-тестов: original baseline vs repaired + ресурсы. */
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
        <ul className="max-h-64 space-y-1.5 overflow-auto text-[10px]">
          {compare.runs.map((run) => (
            <li
              key={run.test_id}
              className="rounded border border-zinc-800 bg-zinc-900/60 px-2 py-1.5 text-zinc-300"
            >
              <div>
                <span className="font-medium text-zinc-200">{run.test_id}</span> {run.name}
                {run.purpose === "exploit_error" || run.expects_original_failure ? (
                  <span className="ml-1 text-amber-300/90">{uiText.testCompareExploit}</span>
                ) : null}
                : <span className={statusClass(run.original_status)}>{run.original_status}</span>
                {" → "}
                <span className={statusClass(run.generated_status)}>{run.generated_status}</span>
                <span className="ml-1 text-zinc-500">{formatResources(run)}</span>
              </div>
              {run.description ? (
                <p className="mt-0.5 text-zinc-400">{run.description}</p>
              ) : null}
              {run.error_description ? (
                <p className="mt-0.5 text-amber-200/80">
                  {uiText.testCompareErrorDesc}: {run.error_description}
                </p>
              ) : null}
              {run.original_status !== "pass" ||
              (run.generated_status !== "pass" && run.generated_status !== "skipped") ? (
                <p className="mt-0.5 break-words text-rose-200/70">{shortDetail(run)}</p>
              ) : null}
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
  if (status === "fail" || status === "error" || status === "timeout") {
    return "text-red-300";
  }
  return "text-zinc-400";
}

function formatResources(run: BehaviorTestRun): string {
  const oWall = run.original_wall_ms;
  const gWall = run.generated_wall_ms;
  if (oWall == null && gWall == null) {
    return "";
  }
  const oCpu = (run.original_cpu_user_ms ?? 0) + (run.original_cpu_sys_ms ?? 0);
  const gCpu = (run.generated_cpu_user_ms ?? 0) + (run.generated_cpu_sys_ms ?? 0);
  const oRss = run.original_max_rss_kb;
  const gRss = run.generated_max_rss_kb;
  const baseline =
    run.resources_vs_baseline && run.resources_vs_baseline !== "n/a"
      ? ` · ${uiText.testCompareBaseline} ${run.resources_vs_baseline}`
      : "";
  const ratios =
    run.wall_ratio != null
      ? ` (×${run.wall_ratio.toFixed(2)}/${(run.cpu_ratio ?? 0).toFixed(2)}/${(run.rss_ratio ?? 0).toFixed(2)})`
      : "";
  return (
    `· ${uiText.testCompareWall} ${oWall ?? "-"}→${gWall ?? "-"}ms` +
    ` · ${uiText.testCompareCpu} ${oCpu || "-"}→${gCpu || "-"}ms` +
    ` · ${uiText.testCompareRss} ${oRss ?? "-"}→${gRss ?? "-"}kb` +
    ratios +
    baseline
  );
}

function shortDetail(run: BehaviorTestRun): string {
  const stderr =
    run.original_status !== "pass" ? run.original_stderr : run.generated_stderr;
  if (stderr && stderr.trim()) {
    return stderr.replace(/\s+/g, " ").slice(0, 220);
  }
  return run.detail.slice(0, 220);
}
