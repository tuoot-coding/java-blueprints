"use client";

import { Palette } from "lucide-react";

import { uiText } from "@/shared/i18n/ru";
import { UI_THEME_IDS, type UiThemeId } from "@/shared/theme/uiTheme";

interface ThemeSwitcherProps {
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

export function ThemeSwitcher({ preference, onChange }: ThemeSwitcherProps) {
  return (
    <label
      className="inline-flex items-center gap-1.5 rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs text-zinc-200"
      title={uiText.themeTitle}
    >
      <Palette size={14} className="shrink-0 text-zinc-400" />
      <span className="sr-only">{uiText.themeTitle}</span>
      <select
        className="max-w-[9.5rem] cursor-pointer bg-transparent text-xs text-zinc-200 outline-none"
        value={preference}
        aria-label={uiText.themeTitle}
        onChange={(event) => onChange(event.target.value as UiThemeId)}
      >
        {UI_THEME_IDS.map((id) => (
          <option key={id} value={id} className="bg-zinc-900 text-zinc-100">
            {THEME_LABELS[id]}
          </option>
        ))}
      </select>
    </label>
  );
}
