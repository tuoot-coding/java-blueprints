import { describe, expect, it } from "vitest";

import { isJavaFileName } from "@/shared/lib/javaFile";

describe("isJavaFileName", () => {
  it("принимает расширение .java без учета регистра", () => {
    expect(isJavaFileName("Main.java")).toBe(true);
    expect(isJavaFileName("Demo.JAVA")).toBe(true);
  });

  it("отклоняет другие расширения", () => {
    expect(isJavaFileName("Main.txt")).toBe(false);
    expect(isJavaFileName("Main.java.bak")).toBe(false);
  });
});
