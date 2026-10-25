/** Операции редактирования модульной логической схемы (связи next/body/else). */

import { isLoopKind, isStructureContainerKind } from "@/shared/lib/schemeTheme";
import type { ScratchBlock, ScratchLink, ScratchProgram } from "@/shared/types/workspace";

const ORDER_LINK_KINDS = new Set(["next", "body", "else", "children"]);

const PROTECTED_KINDS = new Set(["start", "end", "class", "interface", "enum", "record", "method"]);

export type InsertableBlockKind =
  | "variable"
  | "assignment"
  | "expression"
  | "call"
  | "if"
  | "else"
  | "while"
  | "do"
  | "for"
  | "foreach"
  | "switch"
  | "case"
  | "return"
  | "break"
  | "continue"
  | "throw"
  | "try"
  | "catch"
  | "finally"
  | "synchronized";

export type InsertMode = "after" | "body" | "free";

export interface BlockPaletteItem {
  kind: InsertableBlockKind;
  title: string;
  defaultLabel: string;
  snippet: string;
  color: string;
  structural?: boolean;
}

/** Пустые/шаблонные элементы для конструктора (заполняются вручную, связываются руками). */
export const BLOCK_PALETTE: BlockPaletteItem[] = [
  {
    kind: "variable",
    title: "Переменная",
    defaultLabel: "Переменная",
    snippet: "Type name = value;",
    color: "#0d9488",
  },
  {
    kind: "assignment",
    title: "Операция",
    defaultLabel: "Операция",
    snippet: "/* операция */",
    color: "#0891b2",
  },
  {
    kind: "expression",
    title: "Выражение",
    defaultLabel: "Выражение",
    snippet: "/* выражение */;",
    color: "#475569",
  },
  {
    kind: "call",
    title: "Вызов",
    defaultLabel: "Вызов",
    snippet: "methodName();",
    color: "#eab308",
  },
  {
    kind: "if",
    title: "Условие if",
    defaultLabel: "Условие: /* условие */",
    snippet: "if (/* условие */) {\n  \n}",
    color: "#ca8a04",
    structural: true,
  },
  {
    kind: "else",
    title: "Иначе else",
    defaultLabel: "Иначе",
    snippet: "else {\n  \n}",
    color: "#a16207",
    structural: true,
  },
  {
    kind: "while",
    title: "Цикл while",
    defaultLabel: "Цикл while: /* условие */",
    snippet: "while (/* условие */) {\n  \n}",
    color: "#c026d3",
    structural: true,
  },
  {
    kind: "do",
    title: "Цикл do-while",
    defaultLabel: "Цикл do: /* условие */",
    snippet: "do {\n  \n} while (/* условие */);",
    color: "#c026d3",
    structural: true,
  },
  {
    kind: "for",
    title: "Цикл for",
    defaultLabel: "Цикл for: /* инициализация; условие; шаг */",
    snippet: "for (/* init */; /* условие */; /* шаг */) {\n  \n}",
    color: "#db2777",
    structural: true,
  },
  {
    kind: "foreach",
    title: "Цикл for-each",
    defaultLabel: "Цикл for each: /* Type item : items */",
    snippet: "for (/* Type item : items */) {\n  \n}",
    color: "#db2777",
    structural: true,
  },
  {
    kind: "switch",
    title: "switch",
    defaultLabel: "Выбор switch: /* выражение */",
    snippet: "switch (/* выражение */) {\n  default:\n    break;\n}",
    color: "#d97706",
    structural: true,
  },
  {
    kind: "case",
    title: "case",
    defaultLabel: "Ветка case: /* значение */",
    snippet: "case /* ЗНАЧЕНИЕ */:\n  break;",
    color: "#b45309",
    structural: true,
  },
  {
    kind: "try",
    title: "try",
    defaultLabel: "Попытка try",
    snippet: "try {\n  \n}",
    color: "#4f46e5",
    structural: true,
  },
  {
    kind: "catch",
    title: "catch",
    defaultLabel: "Перехват catch: /* Exception e */",
    snippet: "catch (/* Exception e */) {\n  \n}",
    color: "#4338ca",
    structural: true,
  },
  {
    kind: "finally",
    title: "finally",
    defaultLabel: "Наконец finally",
    snippet: "finally {\n  \n}",
    color: "#3730a3",
    structural: true,
  },
  {
    kind: "synchronized",
    title: "synchronized",
    defaultLabel: "Синхронно: /* монитор */",
    snippet: "synchronized (/* this */) {\n  \n}",
    color: "#0f766e",
    structural: true,
  },
  {
    kind: "return",
    title: "Возврат",
    defaultLabel: "Возврат: /* значение */",
    snippet: "return /* значение */;",
    color: "#22c55e",
  },
  {
    kind: "break",
    title: "Прервать",
    defaultLabel: "Прервать",
    snippet: "break;",
    color: "#ef4444",
  },
  {
    kind: "continue",
    title: "Продолжить",
    defaultLabel: "Продолжить",
    snippet: "continue;",
    color: "#ef4444",
  },
  {
    kind: "throw",
    title: "throw",
    defaultLabel: "Исключение: /* new ... */",
    snippet: "throw /* new Exception() */;",
    color: "#b91c1c",
  },
];

/** Пустая схема с одним методом-корнем для конструктора с нуля. */
export function createBlankScratchProgram(methodName: string = "process"): ScratchProgram {
  const methodId = `blank_method_${Date.now().toString(36)}`;
  const moduleId = `blank_mod_${methodId}`;
  const emptySpan = {
    start_byte: 0,
    end_byte: 0,
    start_line: 1,
    start_column: 1,
    end_line: 1,
    end_column: 1,
  };
  return {
    method_name: methodName,
    method_ir_id: methodId,
    root_block_ids: [methodId],
    method_names: [methodName],
    modules: [
      {
        id: moduleId,
        kind: "method",
        name: methodName,
        parent_module_id: null,
        root_block_id: methodId,
        block_ids: [methodId],
      },
    ],
    blocks: [
      {
        id: methodId,
        kind: "method",
        label: `void ${methodName}()`,
        ir_node_id: methodId,
        span: emptySpan,
        parent_id: null,
        nest_level: 0,
        color: "#a855f7",
        links: [],
        source_snippet: `void ${methodName}() {\n  // тело метода\n}\n`,
        module_id: moduleId,
        editable: true,
      },
    ],
  };
}

export const BLANK_SCHEME_JAVA = `public class ScratchScheme {
  void process() {
  }
}
`;

/**
 * Разрешена ли связь: тело контейнера отдельно; next изнутри цикла не уходит наружу.
 * Цикл во внешнем потоке - обычный элемент (in/out), внутри - свой поток.
 */
export function canConnectBlocks(
  program: ScratchProgram,
  sourceId: string,
  targetId: string,
  linkKind: string = "next",
): boolean {
  if (sourceId === targetId) {
    return false;
  }
  const kind = normalizeLinkKind(linkKind);
  const byId = new Map(program.blocks.map((block) => [block.id, block]));
  const source = byId.get(sourceId);
  const target = byId.get(targetId);
  if (!source || !target) {
    return false;
  }
  if (kind === "body") {
    return isCompositeHostKind(source.kind) || isStructureContainerKind(source.kind);
  }
  const sourceIsContainer =
    isStructureContainerKind(source.kind) || isLoopKind(source.kind);
  if (sourceIsContainer && kind === "next") {
    // Внешний выход контейнера: нельзя вести next на собственного ребёнка.
    return target.parent_id !== source.id;
  }
  // Внутренний next/else: только в пределах того же родителя (тело цикла).
  if (source.parent_id) {
    const parent = byId.get(source.parent_id);
    if (parent && (isStructureContainerKind(parent.kind) || isLoopKind(parent.kind))) {
      if (target.parent_id !== source.parent_id && target.id !== source.parent_id) {
        return false;
      }
    }
  }
  return true;
}

export function connectBlocks(
  program: ScratchProgram,
  sourceId: string,
  targetId: string,
  linkKind: string = "next",
): ScratchProgram {
  if (!canConnectBlocks(program, sourceId, targetId, linkKind)) {
    return program;
  }
  const kind = normalizeLinkKind(linkKind);
  const byId = new Map(program.blocks.map((block) => [block.id, block]));
  const source = byId.get(sourceId);
  if (!source || !byId.has(targetId)) {
    return program;
  }

  let blocks = program.blocks.map((block) => {
    if (block.id !== sourceId) {
      // Убираем чужие body/else на тот же target, чтобы не было двух родителей.
      if (
        (kind === "body" || kind === "else") &&
        block.links.some((link) => link.kind === kind && link.target_id === targetId)
      ) {
        return {
          ...block,
          links: block.links.filter(
            (link) => !(link.kind === kind && link.target_id === targetId),
          ),
        };
      }
      return block;
    }
    const withoutSame =
      kind === "next"
        ? block.links.filter((link) => link.kind !== "next")
        : block.links.filter((link) => link.kind !== kind);
    return {
      ...block,
      links: [...withoutSame, { kind, target_id: targetId }],
    };
  });

  // Репарент: body -> внутрь контейнера; next/else внутри узла в контейнере -> тот же parent.
  blocks = blocks.map((block) => {
    if (block.id !== targetId) {
      return block;
    }
    if (kind === "body") {
      return {
        ...block,
        parent_id: sourceId,
        nest_level: source.nest_level + 1,
      };
    }
    if ((kind === "next" || kind === "else") && source.parent_id) {
      const parent = byId.get(source.parent_id);
      return {
        ...block,
        parent_id: source.parent_id,
        nest_level: parent ? parent.nest_level + 1 : block.nest_level,
      };
    }
    return block;
  });

  return { ...program, blocks };
}

export function disconnectBlocks(
  program: ScratchProgram,
  sourceId: string,
  targetId: string,
  linkKind?: string,
): ScratchProgram {
  const blocks = program.blocks.map((block) => {
    if (block.id !== sourceId) {
      return block;
    }
    return {
      ...block,
      links: block.links.filter((link) => {
        if (link.target_id !== targetId) {
          return true;
        }
        if (linkKind && link.kind !== linkKind) {
          return true;
        }
        return !ORDER_LINK_KINDS.has(link.kind);
      }),
    };
  });
  return { ...program, blocks };
}

/**
 * Удаляет блок и его потомков. Перешивает next/body вокруг удалённого узла.
 * start/end/method/class и editable=false не удаляются.
 */
export function deleteBlock(program: ScratchProgram, blockId: string): ScratchProgram {
  const target = program.blocks.find((block) => block.id === blockId);
  if (!target) {
    return program;
  }
  if (target.editable === false || PROTECTED_KINDS.has(target.kind)) {
    return program;
  }

  const removeIds = collectDescendants(program, blockId);
  removeIds.add(blockId);

  const nextOfDeleted =
    target.links.find((link) => link.kind === "next" && !removeIds.has(link.target_id))
      ?.target_id ?? null;

  const blocks = program.blocks
    .filter((block) => !removeIds.has(block.id))
    .map((block) => ({
      ...block,
      links: block.links
        .map((link) => {
          if (!removeIds.has(link.target_id)) {
            return link;
          }
          if (
            (link.kind === "next" || link.kind === "body") &&
            nextOfDeleted &&
            nextOfDeleted !== block.id
          ) {
            return { ...link, target_id: nextOfDeleted };
          }
          return null;
        })
        .filter((link): link is ScratchLink => link !== null),
    }));

  const parentId = target.parent_id;
  const siblings = orderedSiblings({ ...program, blocks }, parentId)
    .map((block) => block.id)
    .filter((id) => !removeIds.has(id));
  return rewriteSiblingNextChain({ ...program, blocks }, parentId, siblings);
}

/**
 * Вставляет блок:
 * - after: в next-цепочку после afterId;
 * - body: первым в тело контейнера;
 * - free: без автосвязей (соединить вручную на схеме).
 */
export function insertBlock(
  program: ScratchProgram,
  kind: InsertableBlockKind,
  options: {
    afterId?: string | null;
    parentId?: string | null;
    intoBodyOfId?: string | null;
    free?: boolean;
  } = {},
): ScratchProgram {
  const palette = BLOCK_PALETTE.find((item) => item.kind === kind);
  if (!palette) {
    return program;
  }

  const newId = `user_${kind}_${Date.now().toString(36)}_${Math.floor(Math.random() * 1e4)}`;
  let parentId: string | null = options.parentId ?? null;
  let insertAfter: string | null = options.afterId ?? null;
  const intoBody = options.intoBodyOfId ?? null;
  const free = Boolean(options.free);

  const methodRoot =
    program.blocks.find((block) => block.kind === "method") ??
    program.blocks.find((block) => block.id === program.method_ir_id);

  // Свободная вставка не зависит от выбранного узла: всегда под корнем метода.
  if (free) {
    parentId = methodRoot?.id ?? program.root_block_ids[0] ?? null;
    insertAfter = null;
  } else if (intoBody) {
    const host = program.blocks.find((block) => block.id === intoBody);
    if (!host) {
      return program;
    }
    parentId = host.id;
    insertAfter = null;
  } else if (insertAfter) {
    const after = program.blocks.find((block) => block.id === insertAfter);
    if (!after) {
      return program;
    }
    parentId = after.parent_id;
  } else if (parentId == null) {
    parentId = methodRoot?.id ?? program.root_block_ids[0] ?? null;
  }

  const nestLevel =
    (program.blocks.find((block) => block.id === parentId)?.nest_level ?? 0) + 1;

  const newBlock: ScratchBlock = {
    id: newId,
    kind,
    label: palette.defaultLabel,
    ir_node_id: newId,
    span: {
      start_byte: 0,
      end_byte: 0,
      start_line: 1,
      start_column: 1,
      end_line: 1,
      end_column: 1,
    },
    parent_id: parentId,
    nest_level: nestLevel,
    color: palette.color,
    links: [],
    source_snippet: palette.snippet,
    module_id: program.blocks.find((block) => block.id === parentId)?.module_id ?? null,
    editable: true,
  };

  let nextProgram: ScratchProgram = { ...program, blocks: [...program.blocks, newBlock] };

  if (free) {
    return nextProgram;
  }

  if (intoBody) {
    const host = nextProgram.blocks.find((block) => block.id === intoBody);
    if (host) {
      const oldBody = host.links.find((link) => link.kind === "body")?.target_id;
      const blocks = nextProgram.blocks.map((block) => {
        if (block.id === newId && oldBody) {
          return {
            ...block,
            links: [
              ...block.links.filter((link) => link.kind !== "next"),
              { kind: "next", target_id: oldBody },
            ],
          };
        }
        if (block.id !== intoBody) {
          return block;
        }
        const withoutBody = block.links.filter((link) => link.kind !== "body");
        return {
          ...block,
          links: [{ kind: "body", target_id: newId }, ...withoutBody],
        };
      });
      nextProgram = { ...program, blocks };
    }
  } else {
    const siblings = orderedSiblings(nextProgram, parentId).map((block) => block.id);
    const filtered = siblings.filter((id) => id !== newId);
    let ordered = filtered;
    if (insertAfter && filtered.includes(insertAfter)) {
      const index = filtered.indexOf(insertAfter);
      ordered = [...filtered.slice(0, index + 1), newId, ...filtered.slice(index + 1)];
    } else {
      ordered = [...filtered, newId];
    }
    nextProgram = rewriteSiblingNextChain(nextProgram, parentId, ordered);
  }

  return nextProgram;
}

export function updateBlockContent(
  program: ScratchProgram,
  blockId: string,
  patch: { label?: string; source_snippet?: string },
): ScratchProgram {
  return {
    ...program,
    blocks: program.blocks.map((block) => {
      if (block.id !== blockId || block.editable === false) {
        return block;
      }
      return {
        ...block,
        label: patch.label ?? block.label,
        source_snippet:
          patch.source_snippet !== undefined ? patch.source_snippet : (block.source_snippet ?? ""),
      };
    }),
  };
}

export function canDeleteBlock(program: ScratchProgram, blockId: string): boolean {
  const block = program.blocks.find((item) => item.id === blockId);
  if (!block) {
    return false;
  }
  return block.editable !== false && !PROTECTED_KINDS.has(block.kind);
}

export function isCompositeHostKind(kind: string): boolean {
  return [
    "if",
    "else",
    "while",
    "do",
    "for",
    "foreach",
    "try",
    "catch",
    "finally",
    "switch",
    "case",
    "synchronized",
    "method",
  ].includes(kind);
}

/** Меняет порядок двух соседних блоков в next-цепочке одного родителя. */
export function moveBlockAmongSiblings(
  program: ScratchProgram,
  blockId: string,
  direction: "up" | "down",
): ScratchProgram {
  const block = program.blocks.find((item) => item.id === blockId);
  if (!block || block.editable === false) {
    return program;
  }
  const siblings = orderedSiblings(program, block.parent_id);
  const index = siblings.findIndex((item) => item.id === blockId);
  if (index < 0) {
    return program;
  }
  const swapWith = direction === "up" ? index - 1 : index + 1;
  if (swapWith < 0 || swapWith >= siblings.length) {
    return program;
  }
  const reordered = [...siblings];
  const temp = reordered[index]!;
  reordered[index] = reordered[swapWith]!;
  reordered[swapWith] = temp;
  return rewriteSiblingNextChain(program, block.parent_id, reordered.map((item) => item.id));
}

export function orderedSiblings(
  program: ScratchProgram,
  parentId: string | null,
): ScratchBlock[] {
  const siblings = program.blocks.filter(
    (block) =>
      block.parent_id === parentId &&
      block.kind !== "parameter" &&
      block.kind !== "start" &&
      block.kind !== "end",
  );
  if (siblings.length <= 1) {
    return siblings;
  }
  const byId = new Map(siblings.map((block) => [block.id, block]));
  const nextMap = new Map<string, string>();
  const targeted = new Set<string>();
  for (const block of siblings) {
    const next = block.links.find((link) => link.kind === "next" && byId.has(link.target_id));
    if (next) {
      nextMap.set(block.id, next.target_id);
      targeted.add(next.target_id);
    }
  }
  const heads = siblings.filter((block) => !targeted.has(block.id));
  const ordered: ScratchBlock[] = [];
  const seen = new Set<string>();
  for (const head of heads.length > 0 ? heads : siblings.slice(0, 1)) {
    let current: string | undefined = head.id;
    while (current && byId.has(current) && !seen.has(current)) {
      seen.add(current);
      ordered.push(byId.get(current)!);
      current = nextMap.get(current);
    }
  }
  for (const block of siblings) {
    if (!seen.has(block.id)) {
      ordered.push(block);
    }
  }
  return ordered;
}

function collectDescendants(program: ScratchProgram, rootId: string): Set<string> {
  const result = new Set<string>();
  let changed = true;
  while (changed) {
    changed = false;
    for (const block of program.blocks) {
      if (result.has(block.id) || block.id === rootId) {
        continue;
      }
      if (block.parent_id && (block.parent_id === rootId || result.has(block.parent_id))) {
        result.add(block.id);
        changed = true;
      }
    }
  }
  return result;
}

function rewriteSiblingNextChain(
  program: ScratchProgram,
  parentId: string | null,
  orderedIds: string[],
): ScratchProgram {
  const idSet = new Set(orderedIds);
  const blocks = program.blocks.map((block) => {
    if (!idSet.has(block.id)) {
      return block;
    }
    const index = orderedIds.indexOf(block.id);
    const withoutNext = block.links.filter((link) => link.kind !== "next");
    if (index >= 0 && index < orderedIds.length - 1) {
      return {
        ...block,
        links: [...withoutNext, { kind: "next", target_id: orderedIds[index + 1]! }],
      };
    }
    return { ...block, links: withoutNext };
  });

  if (parentId && orderedIds.length > 0) {
    return {
      ...program,
      blocks: blocks.map((block) => {
        if (block.id !== parentId) {
          return block;
        }
        const withoutBody = block.links.filter((link) => link.kind !== "body");
        return {
          ...block,
          links: [{ kind: "body", target_id: orderedIds[0]! }, ...withoutBody],
        };
      }),
    };
  }
  return { ...program, blocks };
}

function normalizeLinkKind(raw: string): string {
  if (raw === "else" || raw === "body" || raw === "children" || raw === "next") {
    return raw;
  }
  return "next";
}

export function summarizeSchemeOrder(program: ScratchProgram): string {
  const lines: string[] = [];
  for (const block of program.blocks) {
    const outs = block.links
      .filter((link) => ORDER_LINK_KINDS.has(link.kind))
      .map((link) => `${link.kind}->${link.target_id}`)
      .join(",");
    if (outs) {
      lines.push(`${block.id}:${outs}`);
    }
  }
  return lines.join("|");
}

/** Стабильный ключ структуры схемы (без selection). */
export function schemeStructureKey(program: ScratchProgram): string {
  return program.blocks
    .map((block) => {
      const links = block.links
        .map((link) => `${link.kind}:${link.target_id}`)
        .sort()
        .join(",");
      return `${block.id}|${block.kind}|${block.label}|${block.source_snippet ?? ""}|${links}`;
    })
    .join(";");
}
