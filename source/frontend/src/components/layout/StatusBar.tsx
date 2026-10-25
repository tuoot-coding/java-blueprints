"use client";

import { getApiBaseUrl } from "@/shared/config/env";
import { uiText } from "@/shared/i18n/ru";
import type { BackendConnectionState } from "@/shared/types/health";

interface StatusBarProps {
  connection: BackendConnectionState;
  dirty: boolean;
  fileName: string | null;
}

export function StatusBar({ connection, dirty, fileName }: StatusBarProps) {
  const apiBase = getApiBaseUrl();

  let backendLabel: string = uiText.statusBackendUnknown;
  let toneClass = "text-zinc-400";

  if (connection.kind === "checking") {
    backendLabel = uiText.statusBackendChecking;
    toneClass = "text-amber-400";
  } else if (connection.kind === "ok") {
    backendLabel = `${uiText.statusBackendOk} - ${uiText.statusVersion} ${connection.health.version} - ${uiText.statusUptime} ${connection.health.uptime_seconds.toFixed(1)}s`;
    toneClass = "text-emerald-400";
  } else {
    backendLabel = `${uiText.statusBackendDown}: ${connection.message}`;
    toneClass = "text-red-400";
  }

  return (
    <footer className="flex h-7 shrink-0 items-center gap-3 border-t border-zinc-800 bg-zinc-950 px-3 text-[11px] text-zinc-500">
      <span className={`truncate ${toneClass}`}>{backendLabel}</span>
      <span className="truncate text-zinc-600">{apiBase}</span>
      <span className="ml-auto truncate">
        {fileName ?? uiText.explorerNoFile}
        {dirty ? " *" : ""}
      </span>
    </footer>
  );
}
