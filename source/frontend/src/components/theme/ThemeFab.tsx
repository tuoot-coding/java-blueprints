"use client";

import { Palette, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { uiText } from "@/shared/i18n/ru";
import { UI_THEME_IDS, type UiThemeId } from "@/shared/theme/uiTheme";

interface ThemeFabProps {
  preference: UiThemeId;
  onChange: (theme: UiThemeId) => void;
}

const THEME_LABELS: Record<UiThemeId, string> = {
  dark: uiText.themeDark,
  light: uiText.themeLight,
  system: uiText.themeSystem,
  neon: uiText.themeNeon,
  terminal: uiText.themeTerminal,
  galactic: uiText.themeGalactic,
};

/** Плавающая кнопка тем в углу экрана (portal в body, поверх панелей). */
export function ThemeFab({ preference, onChange }: ThemeFabProps) {
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!open) {
      return;
    }
    function onDocClick(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (!mounted || typeof document === "undefined") {
    return null;
  }

  return createPortal(
    <div
      ref={rootRef}
      className="pointer-events-none fixed bottom-12 right-4"
      style={{ zIndex: 10000 }}
    >
      {open ? (
        <div className="pointer-events-auto mb-2 w-52 overflow-hidden rounded-xl border border-zinc-600 bg-zinc-950 shadow-2xl">
          <div className="flex items-center justify-between border-b border-zinc-800 px-3 py-2">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-zinc-400">
              {uiText.themeTitle}
            </span>
            <button
              type="button"
              className="rounded p-0.5 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100"
              aria-label={uiText.themeClose}
              onClick={() => setOpen(false)}
            >
              <X size={14} />
            </button>
          </div>
          <ul className="max-h-64 overflow-auto p-1.5">
            {UI_THEME_IDS.map((id) => {
              const active = preference === id;
              return (
                <li key={id}>
                  <button
                    type="button"
                    className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-xs ${
                      active
                        ? "bg-sky-950/60 text-sky-100 ring-1 ring-sky-700"
                        : "text-zinc-200 hover:bg-zinc-800"
                    }`}
                    onClick={() => {
                      onChange(id);
                      setOpen(false);
                    }}
                  >
                    <span
                      className="h-3 w-3 shrink-0 rounded-full border border-zinc-600"
                      style={{ backgroundImage: themeSwatch(id) }}
                      aria-hidden
                    />
                    {THEME_LABELS[id]}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
      <button
        type="button"
        title={uiText.themeTitle}
        aria-label={uiText.themeTitle}
        aria-expanded={open}
        className="pointer-events-auto flex h-12 w-12 items-center justify-center rounded-full border-2 border-sky-500 bg-zinc-900 text-sky-100 shadow-xl shadow-black/50 ring-2 ring-sky-500/30 transition hover:border-sky-400 hover:bg-zinc-800"
        onClick={() => setOpen((value) => !value)}
      >
        <Palette size={20} />
      </button>
    </div>,
    document.body,
  );
}

function themeSwatch(id: UiThemeId): string {
  switch (id) {
    case "light":
      return "linear-gradient(#e4e4e7,#e4e4e7)";
    case "system":
      return "linear-gradient(90deg,#18181b 50%,#f4f4f5 50%)";
    case "neon":
      return "linear-gradient(#d946ef,#22d3ee)";
    case "terminal":
      return "linear-gradient(#22c55e,#14532d)";
    case "galactic":
      return "linear-gradient(#818cf8,#4c1d95)";
    case "dark":
    default:
      return "linear-gradient(#27272a,#09090b)";
  }
}
