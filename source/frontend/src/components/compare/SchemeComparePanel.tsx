"use client";

import { uiText } from "@/shared/i18n/ru";
import type { SchemeCompare } from "@/shared/types/workspace";

interface SchemeComparePanelProps {
  compare: SchemeCompare;
  compact?: boolean;
}

export function SchemeComparePanel({ compare, compact = false }: SchemeComparePanelProps) {
  const similarityPct = Math.round(compare.structural_similarity * 100);
  return (
    <section
      className={`flex min-h-0 flex-col border border-zinc-800 bg-zinc-950 ${
        compact ? "rounded" : "flex-1"
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-800 px-3 py-1.5">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
          {uiText.schemeCompareTitle}
        </span>
        <div className="flex flex-wrap gap-2 text-[10px] text-zinc-400">
          <span>
            {uiText.schemeCompareSimilarity}: {similarityPct}%
          </span>
          <span className={compare.changed ? "text-amber-300" : "text-emerald-300"}>
            {compare.changed ? uiText.schemeCompareChanged : uiText.schemeCompareSame}
          </span>
          <span>
            {compare.original_block_count} → {compare.generated_block_count} blocks
          </span>
          <span>
            {compare.original_module_count} → {compare.generated_module_count} modules
          </span>
        </div>
      </div>
      {(compare.methods_added.length > 0 || compare.methods_removed.length > 0) && (
        <div className="border-b border-zinc-800 px-3 py-1.5 text-[11px] text-zinc-400">
          {compare.methods_added.length > 0
            ? `+ ${compare.methods_added.join(", ")}`
            : null}
          {compare.methods_added.length > 0 && compare.methods_removed.length > 0 ? " · " : null}
          {compare.methods_removed.length > 0
            ? `− ${compare.methods_removed.join(", ")}`
            : null}
        </div>
      )}
      <div className={`grid min-h-0 grid-cols-2 gap-px bg-zinc-800 ${compact ? "max-h-48" : "flex-1"}`}>
        <OutlinePane title={uiText.schemeCompareOriginal} outline={compare.outline_original} />
        <OutlinePane title={uiText.schemeCompareGenerated} outline={compare.outline_generated} />
      </div>
    </section>
  );
}

function OutlinePane({ title, outline }: { title: string; outline: string }) {
  return (
    <div className="flex min-h-0 flex-col bg-zinc-950">
      <div className="border-b border-zinc-800 px-2 py-1 text-[10px] uppercase tracking-wide text-zinc-500">
        {title}
      </div>
      <pre className="min-h-0 flex-1 overflow-auto p-2 font-mono text-[10px] leading-relaxed text-zinc-300 whitespace-pre">
        {outline}
      </pre>
    </div>
  );
}
