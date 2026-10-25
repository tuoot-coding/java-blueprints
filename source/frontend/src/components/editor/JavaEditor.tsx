"use client";

import Editor, { type OnChange, type OnMount } from "@monaco-editor/react";
import { useEffect, useRef } from "react";

import { uiText } from "@/shared/i18n/ru";
import {
  diagnosticsToMonacoMarkers,
  PARSER_MARKER_OWNER,
  type MonacoMarkerLike,
} from "@/shared/lib/monacoMarkers";
import type { SyntaxDiagnostic } from "@/shared/types/parser";
import type { ResolvedUiTheme } from "@/shared/theme/uiTheme";

interface JavaEditorProps {
  value: string;
  onChange: (value: string) => void;
  diagnostics: SyntaxDiagnostic[];
  revealPosition: { line: number; column: number } | null;
  collapsed: boolean;
  onToggleCollapsed: () => void;
  uiTheme: ResolvedUiTheme;
}

const MONACO_THEME_IDS = {
  light: "jb-light",
  dark: "jb-dark",
  neon: "jb-neon",
  terminal: "jb-terminal",
  galactic: "jb-galactic",
} as const;

export function JavaEditor({
  value,
  onChange,
  diagnostics,
  revealPosition,
  collapsed,
  onToggleCollapsed,
  uiTheme,
}: JavaEditorProps) {
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null);
  const monacoRef = useRef<Parameters<OnMount>[1] | null>(null);
  const monacoTheme = MONACO_THEME_IDS[uiTheme] ?? MONACO_THEME_IDS.dark;

  const handleMount: OnMount = (editorInstance, monacoInstance) => {
    editorRef.current = editorInstance;
    monacoRef.current = monacoInstance;
    registerMonacoThemes(monacoInstance);
    monacoInstance.editor.setTheme(monacoTheme);
    applyMarkers(monacoInstance, editorInstance.getModel(), diagnostics);
  };

  const handleChange: OnChange = (nextValue) => {
    onChange(nextValue ?? "");
  };

  useEffect(() => {
    const monacoInstance = monacoRef.current;
    const editorInstance = editorRef.current;
    if (!monacoInstance || !editorInstance) {
      return;
    }
    applyMarkers(monacoInstance, editorInstance.getModel(), diagnostics);
  }, [diagnostics]);

  useEffect(() => {
    const monacoInstance = monacoRef.current;
    if (!monacoInstance) {
      return;
    }
    registerMonacoThemes(monacoInstance);
    monacoInstance.editor.setTheme(monacoTheme);
  }, [monacoTheme]);

  useEffect(() => {
    if (!revealPosition || !editorRef.current || collapsed) {
      return;
    }
    editorRef.current.revealPositionInCenter({
      lineNumber: revealPosition.line,
      column: revealPosition.column,
    });
    editorRef.current.setPosition({
      lineNumber: revealPosition.line,
      column: revealPosition.column,
    });
    editorRef.current.focus();
  }, [revealPosition, collapsed]);

  return (
    <section className="flex h-full min-h-0 flex-col bg-zinc-950">
      <div className="flex shrink-0 items-center justify-between border-b border-zinc-800 px-3 py-1.5">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
          {uiText.editorTitle}
          <span className="ml-2 normal-case tracking-normal text-zinc-600">
            {uiText.editorLanguage}
          </span>
        </span>
        <button
          type="button"
          title={collapsed ? uiText.editorExpand : uiText.editorCollapse}
          aria-label={collapsed ? uiText.editorExpand : uiText.editorCollapse}
          className="rounded border border-zinc-700 px-2 py-0.5 text-[10px] font-semibold leading-none text-zinc-200 hover:bg-zinc-800"
          onClick={onToggleCollapsed}
        >
          {collapsed ? uiText.expandToggle : uiText.collapseToggle}
        </button>
      </div>
      {collapsed ? null : (
        <div className="relative min-h-0 flex-1">
          <Editor
            language="java"
            theme={monacoTheme}
            value={value}
            onChange={handleChange}
            onMount={handleMount}
            loading={
              <div className="flex h-full items-center justify-center text-xs text-zinc-500">
                Monaco...
              </div>
            }
            options={{
              fontSize: 13,
              minimap: { enabled: false },
              scrollBeyondLastLine: false,
              automaticLayout: true,
              tabSize: 4,
              wordWrap: "on",
              renderWhitespace: "selection",
              padding: { top: 8 },
            }}
          />
          {value.length === 0 ? (
            <div className="pointer-events-none absolute inset-x-0 top-10 px-4 text-center text-xs text-zinc-600">
              {uiText.editorEmpty}
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}

function applyMarkers(
  monacoInstance: Parameters<OnMount>[1],
  model: ReturnType<Parameters<OnMount>[0]["getModel"]>,
  diagnostics: SyntaxDiagnostic[],
): void {
  if (!model) {
    return;
  }
  const markers: MonacoMarkerLike[] = diagnosticsToMonacoMarkers(diagnostics);
  monacoInstance.editor.setModelMarkers(model, PARSER_MARKER_OWNER, markers);
}

function registerMonacoThemes(monacoInstance: Parameters<OnMount>[1]): void {
  monacoInstance.editor.defineTheme("jb-light", {
    base: "vs",
    inherit: true,
    rules: [],
    colors: {
      "editor.background": "#ffffff",
      "editor.foreground": "#18181b",
      "editorLineNumber.foreground": "#a1a1aa",
      "editor.selectionBackground": "#bae6fd88",
      "editorCursor.foreground": "#0284c7",
    },
  });
  monacoInstance.editor.defineTheme("jb-dark", {
    base: "vs-dark",
    inherit: true,
    rules: [],
    colors: {
      "editor.background": "#09090b",
      "editor.foreground": "#f4f4f5",
      "editorLineNumber.foreground": "#71717a",
      "editor.selectionBackground": "#0ea5e966",
      "editorCursor.foreground": "#38bdf8",
    },
  });
  monacoInstance.editor.defineTheme("jb-neon", {
    base: "vs-dark",
    inherit: true,
    rules: [],
    colors: {
      "editor.background": "#05010f",
      "editor.foreground": "#f5d0fe",
      "editorLineNumber.foreground": "#a855f7",
      "editor.selectionBackground": "#d946ef44",
      "editorCursor.foreground": "#22d3ee",
    },
  });
  monacoInstance.editor.defineTheme("jb-terminal", {
    base: "vs-dark",
    inherit: true,
    rules: [],
    colors: {
      "editor.background": "#052e16",
      "editor.foreground": "#bbf7d0",
      "editorLineNumber.foreground": "#4ade80",
      "editor.selectionBackground": "#22c55e44",
      "editorCursor.foreground": "#86efac",
    },
  });
  monacoInstance.editor.defineTheme("jb-galactic", {
    base: "vs-dark",
    inherit: true,
    rules: [],
    colors: {
      "editor.background": "#0b1026",
      "editor.foreground": "#e0e7ff",
      "editorLineNumber.foreground": "#818cf8",
      "editor.selectionBackground": "#6366f144",
      "editorCursor.foreground": "#a5b4fc",
    },
  });
}
