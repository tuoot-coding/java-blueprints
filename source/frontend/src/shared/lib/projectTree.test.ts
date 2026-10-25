import { describe, expect, it } from "vitest";

import { buildProjectTree, findProjectFile } from "@/shared/lib/projectTree";

describe("projectTree", () => {
  it("строит дерево папок и файлов", () => {
    const tree = buildProjectTree([
      { path: "demo/src/Main.java", name: "Main.java", text: "class Main {}" },
      { path: "demo/src/util/Helper.java", name: "Helper.java", text: "class Helper {}" },
    ]);
    expect(tree).toHaveLength(1);
    expect(tree[0]!.name).toBe("demo");
    expect(tree[0]!.children?.[0]?.name).toBe("src");
    const src = tree[0]!.children?.[0];
    expect(src?.children?.some((node) => node.name === "Main.java")).toBe(true);
    expect(src?.children?.some((node) => node.name === "util")).toBe(true);
  });

  it("findProjectFile находит по пути", () => {
    const files = [
      { path: "a/A.java", name: "A.java", text: "A" },
      { path: "b/B.java", name: "B.java", text: "B" },
    ];
    expect(findProjectFile(files, "b/B.java")?.text).toBe("B");
  });
});
