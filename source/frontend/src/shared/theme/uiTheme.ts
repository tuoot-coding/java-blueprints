/** Темы оформления UI. Значение system разрешается в dark/light по ОС. */

export const UI_THEME_STORAGE_KEY = "jb.ui-theme";

export const UI_THEME_IDS = [
  "dark",
  "light",
  "system",
  "neon",
  "terminal",
  "galactic",
] as const;

export type UiThemeId = (typeof UI_THEME_IDS)[number];

/** Фактически применяемый data-theme (без system). */
export type ResolvedUiTheme = Exclude<UiThemeId, "system">;

export function isUiThemeId(value: string | null | undefined): value is UiThemeId {
  return Boolean(value && (UI_THEME_IDS as readonly string[]).includes(value));
}

export function readStoredUiTheme(): UiThemeId {
  if (typeof window === "undefined") {
    return "dark";
  }
  try {
    const raw = window.localStorage.getItem(UI_THEME_STORAGE_KEY);
    return isUiThemeId(raw) ? raw : "dark";
  } catch {
    return "dark";
  }
}

export function prefersLightScheme(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  return window.matchMedia("(prefers-color-scheme: light)").matches;
}

export function resolveUiTheme(preference: UiThemeId): ResolvedUiTheme {
  if (preference === "system") {
    return prefersLightScheme() ? "light" : "dark";
  }
  return preference;
}

export function applyUiThemeToDocument(preference: UiThemeId): ResolvedUiTheme {
  const resolved = resolveUiTheme(preference);
  if (typeof document !== "undefined") {
    document.documentElement.setAttribute("data-theme", resolved);
    document.documentElement.setAttribute("data-theme-pref", preference);
    document.documentElement.style.colorScheme =
      resolved === "light" ? "light" : "dark";
  }
  return resolved;
}

export function persistUiTheme(preference: UiThemeId): void {
  try {
    window.localStorage.setItem(UI_THEME_STORAGE_KEY, preference);
  } catch {
    // ignore quota / private mode
  }
}
