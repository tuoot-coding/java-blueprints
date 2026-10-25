"use client";

import { FileCode2, Save, SearchCode, UserRound } from "lucide-react";
import { useRef, type ReactNode } from "react";

import { ThemeSwitcher } from "@/components/theme/ThemeSwitcher";
import { uiText } from "@/shared/i18n/ru";
import type { UiThemeId } from "@/shared/theme/uiTheme";

interface HeaderToolbarProps {
  fileName: string | null;
  dirty: boolean;
  parseBusy: boolean;
  themePreference: UiThemeId;
  onThemeChange: (theme: UiThemeId) => void;
  onOpenFile: (file: File) => void;
  onSaveLocal: () => void;
  onSaveAs?: () => void;
  onParse: () => void;
  authLabel: string;
  authHint?: string;
  onAuthClick: () => void;
}

export function HeaderToolbar({
  fileName,
  dirty,
  parseBusy,
  themePreference,
  onThemeChange,
  onOpenFile,
  onSaveLocal,
  onSaveAs,
  onParse,
  authLabel,
  authHint,
  onAuthClick,
}: HeaderToolbarProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <header className="flex h-12 shrink-0 items-center gap-3 border-b border-zinc-800 bg-zinc-950/90 px-3 backdrop-blur-sm">
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-semibold tracking-wide text-zinc-100">
          {uiText.appName}
          <span className="ml-2 text-xs font-normal text-zinc-500">{uiText.appSubtitle}</span>
        </div>
        <div className="truncate text-xs text-zinc-500">
          {fileName ?? uiText.projectUntitled}
          {" - "}
          {dirty ? uiText.projectDirty : uiText.projectClean}
        </div>
      </div>

      <div className="flex items-center gap-2">
        <ThemeSwitcher preference={themePreference} onChange={onThemeChange} />
        <input
          ref={inputRef}
          type="file"
          accept=".java,text/x-java-source"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            if (file) {
              onOpenFile(file);
            }
          }}
        />
        <ToolbarButton
          icon={<FileCode2 size={14} />}
          label={uiText.actionOpenJava}
          onClick={() => inputRef.current?.click()}
        />
        <ToolbarButton
          icon={<Save size={14} />}
          label={uiText.actionSaveLocal}
          onClick={onSaveLocal}
        />
        {onSaveAs ? (
          <ToolbarButton
            icon={<Save size={14} />}
            label={uiText.editorSaveAs}
            onClick={onSaveAs}
          />
        ) : null}
        <ToolbarButton
          icon={<SearchCode size={14} />}
          label={parseBusy ? uiText.actionParseBusy : uiText.actionParse}
          onClick={onParse}
          disabled={parseBusy}
        />
        <ToolbarButton
          icon={<UserRound size={14} />}
          label={authLabel}
          title={authHint ?? authLabel}
          onClick={onAuthClick}
        />
      </div>
    </header>
  );
}

function ToolbarButton({
  icon,
  label,
  onClick,
  disabled = false,
  title,
}: {
  icon: ReactNode;
  label: string;
  onClick?: () => void;
  disabled?: boolean;
  title?: string;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      title={title ?? label}
      onClick={onClick}
      className="inline-flex items-center gap-1.5 rounded border border-zinc-700 bg-zinc-900 px-2.5 py-1.5 text-xs text-zinc-200 transition hover:border-zinc-500 hover:bg-zinc-800 disabled:cursor-not-allowed disabled:border-zinc-800 disabled:bg-zinc-950 disabled:text-zinc-600"
    >
      {icon}
      <span className="inline">{label}</span>
    </button>
  );
}
