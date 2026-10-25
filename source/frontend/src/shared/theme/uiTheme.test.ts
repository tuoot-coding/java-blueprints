import { describe, expect, it } from "vitest";

import {
  isUiThemeId,
  resolveUiTheme,
  UI_THEME_IDS,
} from "@/shared/theme/uiTheme";

describe("uiTheme", () => {
  it("принимает все объявленные id", () => {
    for (const id of UI_THEME_IDS) {
      expect(isUiThemeId(id)).toBe(true);
    }
    expect(isUiThemeId("unknown")).toBe(false);
  });

  it("system резолвится в dark или light", () => {
    const resolved = resolveUiTheme("system");
    expect(resolved === "dark" || resolved === "light").toBe(true);
  });

  it("именованные темы не меняются при resolve", () => {
    expect(resolveUiTheme("neon")).toBe("neon");
    expect(resolveUiTheme("terminal")).toBe("terminal");
    expect(resolveUiTheme("galactic")).toBe("galactic");
    expect(resolveUiTheme("dark")).toBe("dark");
    expect(resolveUiTheme("light")).toBe("light");
  });
});
