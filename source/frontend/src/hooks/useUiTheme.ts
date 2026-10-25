"use client";

import { useEffect, useState } from "react";

import {
  applyUiThemeToDocument,
  persistUiTheme,
  readStoredUiTheme,
  resolveUiTheme,
  type ResolvedUiTheme,
  type UiThemeId,
} from "@/shared/theme/uiTheme";

export function useUiTheme() {
  const [preference, setPreference] = useState<UiThemeId>("dark");
  const [resolved, setResolved] = useState<ResolvedUiTheme>("dark");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const stored = readStoredUiTheme();
    setPreference(stored);
    setResolved(applyUiThemeToDocument(stored));
    setReady(true);

    const media = window.matchMedia("(prefers-color-scheme: light)");
    function onSchemeChange() {
      setPreference((current) => {
        if (current === "system") {
          setResolved(applyUiThemeToDocument("system"));
        }
        return current;
      });
    }
    media.addEventListener("change", onSchemeChange);
    return () => media.removeEventListener("change", onSchemeChange);
  }, []);

  function setTheme(next: UiThemeId) {
    setPreference(next);
    persistUiTheme(next);
    setResolved(applyUiThemeToDocument(next));
  }

  return {
    preference,
    resolved,
    ready,
    setTheme,
    effective: resolveUiTheme(preference),
  };
}
