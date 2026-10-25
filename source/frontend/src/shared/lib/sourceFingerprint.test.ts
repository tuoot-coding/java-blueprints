import { describe, expect, it } from "vitest";

import { fingerprintSource } from "@/shared/lib/sourceFingerprint";

describe("fingerprintSource", () => {
  it("не включает полный исходник в отпечаток", () => {
    const source = "class A { int m() { return 1; } }\n".repeat(200);
    const fp = fingerprintSource(source);
    expect(fp.length).toBeLessThan(80);
    expect(fp.startsWith(`${source.length}:`)).toBe(true);
    expect(fp.includes("class A")).toBe(false);
  });

  it("одинаков для одинакового текста", () => {
    const source = "class B {}";
    expect(fingerprintSource(source)).toBe(fingerprintSource(source));
  });

  it("меняется при правке", () => {
    expect(fingerprintSource("class A {}")).not.toBe(fingerprintSource("class B {}"));
  });
});
