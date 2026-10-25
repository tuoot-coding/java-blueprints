"use client";

import { uiText } from "@/shared/i18n/ru";
import { roleTitle } from "@/shared/lib/schemeTheme";
import type { ScratchProgram } from "@/shared/types/workspace";

interface PropertiesInspectorProps {
  scratch: ScratchProgram | null;
  selectedBlockId: string | null;
  compact?: boolean;
}

export function PropertiesInspector({
  scratch,
  selectedBlockId,
}: PropertiesInspectorProps) {
  const selected = scratch?.blocks.find((block) => block.id === selectedBlockId) ?? null;
  const code = (selected?.source_snippet ?? "").trim() || selected?.label?.trim() || "";

  return (
    <section className="flex min-h-0 flex-col border-t border-zinc-800 bg-zinc-950">
      <div className="border-b border-zinc-800 px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
        {uiText.inspectorTitle}
      </div>
      <div className="flex-1 space-y-2 overflow-auto p-3 text-xs leading-relaxed text-zinc-400">
        {!selected ? <p>{uiText.inspectorEmpty}</p> : null}
        {selected ? (
          <div className="space-y-2 rounded border border-zinc-800 bg-zinc-900/50 p-2">
            <p className="text-sm font-medium text-zinc-200">{selected.label}</p>
            <p className="text-[11px] text-zinc-500">
              {uiText.inspectorKind}: {roleTitle(selected.kind)}
            </p>
            <div>
              <p className="mb-1 text-[11px] font-semibold uppercase text-zinc-500">
                {uiText.inspectorCode}
              </p>
              {code ? (
                <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-words rounded border border-zinc-800 bg-zinc-950/80 p-2 font-mono text-[11px] text-zinc-300">
                  {code}
                </pre>
              ) : (
                <p className="text-[11px] text-zinc-600">{uiText.inspectorNoCode}</p>
              )}
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}
