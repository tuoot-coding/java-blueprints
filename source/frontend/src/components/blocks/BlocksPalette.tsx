"use client";

import { uiText } from "@/shared/i18n/ru";
import type { ScratchBlock } from "@/shared/types/workspace";

interface BlocksPaletteProps {
  blocks: ScratchBlock[];
  selectedId: string | null;
  onSelect: (blockId: string) => void;
}

const KIND_ORDER = [
  "class",
  "method",
  "start",
  "end",
  "parameter",
  "if",
  "else",
  "while",
  "do",
  "for",
  "foreach",
  "try",
  "catch",
  "finally",
  "variable",
  "assignment",
  "call",
  "return",
  "break",
  "continue",
  "throw",
  "expression",
  "unsupported",
  "block",
];

export function BlocksPalette({ blocks, selectedId, onSelect }: BlocksPaletteProps) {
  const visible = [...blocks].sort((left, right) => {
    const leftRank = KIND_ORDER.indexOf(left.kind);
    const rightRank = KIND_ORDER.indexOf(right.kind);
    const safeLeft = leftRank < 0 ? 999 : leftRank;
    const safeRight = rightRank < 0 ? 999 : rightRank;
    if (safeLeft !== safeRight) {
      return safeLeft - safeRight;
    }
    return left.span.start_line - right.span.start_line;
  });

  return (
    <section className="flex h-full flex-col border-r border-zinc-800 bg-zinc-950">
      <div className="border-b border-zinc-800 px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
        {uiText.blocksTitle}
      </div>
      <div className="flex-1 overflow-auto p-3 text-xs leading-relaxed text-zinc-500">
        {visible.length === 0 ? (
          <p>{uiText.blocksEmpty}</p>
        ) : (
          <ul className="space-y-2">
            {visible.map((block) => (
              <li key={block.id}>
                <button
                  type="button"
                  className={`w-full rounded-lg border-2 px-2 py-2 text-left shadow-[inset_0_-2px_0_rgba(0,0,0,0.2)] transition ${
                    selectedId === block.id ? "ring-2 ring-yellow-300" : ""
                  }`}
                  style={{
                    background: block.color,
                    borderColor: "rgba(0,0,0,0.25)",
                    color: "#0f172a",
                  }}
                  onClick={() => onSelect(block.id)}
                >
                  <div className="truncate text-[11px] font-bold">{block.label}</div>
                  <div className="mt-0.5 truncate text-[10px] opacity-70">
                    {block.kind} · {block.span.start_line}:{block.span.start_column}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
