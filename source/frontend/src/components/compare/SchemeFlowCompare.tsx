"use client";

import { useState } from "react";

import { GraphWorkspace } from "@/components/graph/GraphWorkspace";
import { uiText } from "@/shared/i18n/ru";
import type { ScratchProgram } from "@/shared/types/workspace";

interface SchemeFlowCompareProps {
  original: ScratchProgram | null | undefined;
  generated: ScratchProgram | null | undefined;
  /** Занимает слот основной блок-схемы на время сравнения. */
  fillSlot?: boolean;
  collapsed?: boolean;
  onToggleCollapsed?: () => void;
}

/** Две логические блок-схемы рядом: до и после. Сворачивается и меняет высоту. */
export function SchemeFlowCompare({
  original,
  generated,
  fillSlot = false,
  collapsed: collapsedProp,
  onToggleCollapsed,
}: SchemeFlowCompareProps) {
  const [localCollapsed, setLocalCollapsed] = useState(false);
  const [heightPx, setHeightPx] = useState(320);
  const collapsed = collapsedProp ?? localCollapsed;

  if (!original && !generated) {
    return null;
  }

  function toggleCollapsed() {
    if (onToggleCollapsed) {
      onToggleCollapsed();
      return;
    }
    setLocalCollapsed((value) => !value);
  }

  return (
    <section
      className={`flex flex-col border-zinc-800 bg-zinc-950 ${
        fillSlot ? "h-full min-h-0 border-0" : "min-h-0 border-t"
      }`}
    >
      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-zinc-800 px-3 py-1.5">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
          {uiText.schemeFlowCompareTitle}
        </span>
        <div className="flex items-center gap-1">
          {!collapsed && !fillSlot ? (
            <>
              <button
                type="button"
                className="rounded border border-zinc-700 px-1.5 py-0.5 text-[10px] text-zinc-300 hover:bg-zinc-800"
                onClick={() => setHeightPx((value) => Math.max(180, value - 60))}
              >
                {uiText.schemeFlowCompareSmaller}
              </button>
              <button
                type="button"
                className="rounded border border-zinc-700 px-1.5 py-0.5 text-[10px] text-zinc-300 hover:bg-zinc-800"
                onClick={() => setHeightPx((value) => Math.min(640, value + 60))}
              >
                {uiText.schemeFlowCompareLarger}
              </button>
            </>
          ) : null}
          <button
            type="button"
            title={
              collapsed ? uiText.schemeFlowCompareExpand : uiText.schemeFlowCompareCollapse
            }
            aria-label={
              collapsed ? uiText.schemeFlowCompareExpand : uiText.schemeFlowCompareCollapse
            }
            className="rounded border border-zinc-700 px-2 py-0.5 text-[10px] font-semibold leading-none text-zinc-200 hover:bg-zinc-800"
            onClick={toggleCollapsed}
          >
            {collapsed ? uiText.expandToggle : uiText.collapseToggle}
          </button>
        </div>
      </div>
      {collapsed ? null : (
        <div
          className={`grid min-h-0 flex-1 grid-cols-2 gap-px bg-zinc-800 ${fillSlot ? "" : ""}`}
          style={fillSlot ? undefined : { height: heightPx }}
        >
          <div className="flex min-h-0 flex-col bg-zinc-950">
            <div className="border-b border-zinc-800 px-2 py-1 text-[10px] uppercase tracking-wide text-zinc-500">
              {uiText.schemeFlowCompareOriginal}
            </div>
            <div className="min-h-0 flex-1">
              <GraphWorkspace scratch={original ?? null} stale={false} compact />
            </div>
          </div>
          <div className="flex min-h-0 flex-col bg-zinc-950">
            <div className="border-b border-zinc-800 px-2 py-1 text-[10px] uppercase tracking-wide text-zinc-500">
              {uiText.schemeFlowCompareGenerated}
            </div>
            <div className="min-h-0 flex-1">
              <GraphWorkspace scratch={generated ?? null} stale={false} compact />
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
