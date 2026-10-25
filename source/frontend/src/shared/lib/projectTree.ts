/** Дерево локального проекта из путей файлов (без серверного хранения). */

export interface ProjectFileEntry {
  path: string;
  name: string;
  text: string;
}

export interface ProjectTreeNode {
  id: string;
  name: string;
  kind: "folder" | "file";
  path: string;
  children?: ProjectTreeNode[];
}

function normalizePath(raw: string): string {
  return raw.replace(/\\/g, "/").replace(/^\/+/, "");
}

/** Собирает дерево папок/файлов из плоского списка. */
export function buildProjectTree(files: ProjectFileEntry[]): ProjectTreeNode[] {
  interface Mutable {
    id: string;
    name: string;
    kind: "folder" | "file";
    path: string;
    childrenMap: Map<string, Mutable>;
  }

  const root = new Map<string, Mutable>();

  function ensureFolder(map: Map<string, Mutable>, name: string, path: string): Mutable {
    let node = map.get(name);
    if (!node) {
      node = {
        id: `dir:${path}`,
        name,
        kind: "folder",
        path,
        childrenMap: new Map(),
      };
      map.set(name, node);
    }
    return node;
  }

  for (const file of files) {
    const path = normalizePath(file.path);
    const parts = path.split("/").filter(Boolean);
    if (parts.length === 0) {
      continue;
    }
    let map = root;
    let prefix = "";
    for (let index = 0; index < parts.length; index += 1) {
      const part = parts[index]!;
      prefix = prefix ? `${prefix}/${part}` : part;
      const isFile = index === parts.length - 1;
      if (isFile) {
        map.set(part, {
          id: `file:${path}`,
          name: part,
          kind: "file",
          path,
          childrenMap: new Map(),
        });
      } else {
        const folder = ensureFolder(map, part, prefix);
        map = folder.childrenMap;
      }
    }
  }

  function toNodes(map: Map<string, Mutable>): ProjectTreeNode[] {
    return [...map.values()]
      .sort((left, right) => {
        if (left.kind !== right.kind) {
          return left.kind === "folder" ? -1 : 1;
        }
        return left.name.localeCompare(right.name, "ru");
      })
      .map((node) => ({
        id: node.id,
        name: node.name,
        kind: node.kind,
        path: node.path,
        children: node.kind === "folder" ? toNodes(node.childrenMap) : undefined,
      }));
  }

  return toNodes(root);
}

export async function readProjectFromFileList(
  list: FileList | File[],
): Promise<ProjectFileEntry[]> {
  const files = Array.from(list);
  const javaFiles = files.filter((file) => file.name.toLowerCase().endsWith(".java"));
  const entries: ProjectFileEntry[] = [];
  for (const file of javaFiles) {
    const path = normalizePath((file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name);
    const text = await file.text();
    entries.push({
      path,
      name: file.name,
      text,
    });
  }
  entries.sort((left, right) => left.path.localeCompare(right.path, "ru"));
  return entries;
}

export function findProjectFile(
  files: ProjectFileEntry[],
  path: string,
): ProjectFileEntry | undefined {
  const normalized = normalizePath(path);
  return files.find((file) => normalizePath(file.path) === normalized);
}
