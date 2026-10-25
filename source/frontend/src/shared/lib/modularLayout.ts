/** Иерархическая раскладка: Top-Down, контейнеры структур, без наложений. */

import type { Edge, Node } from "@xyflow/react";

import { scratchFlowNodeType, type ScratchNodeData } from "@/components/graph/scratchNodes";
import { uiText } from "@/shared/i18n/ru";
import type { SchemeMarker } from "@/shared/lib/schemeTheme";
import {
  accentForKind,
  containerTitle,
  isExitKind,
  isStructureContainerKind,
  roleTitle,
  schemeColors,
} from "@/shared/lib/schemeTheme";
import type { ScratchBlock, ScratchProgram } from "@/shared/types/workspace";

const COL_W = 248;
const NODE_H = 82;
const DECISION_H = 128;
const METHOD_H = 96;
const CONTAINER_HEADER = 62;
const PAD = 22;
/** Минимальная высота тела пустого цикла/контейнера (зона для размещения). */
const EMPTY_BODY_H = 160;
const GAP_Y = 48;
const GAP_X = 72;
const BRANCH_X = COL_W + GAP_X;
const MIN_CARD_W = 160;
const MAX_CARD_W = 420;
const MIN_CARD_H = 64;
const MAX_CARD_H = 280;
const CALLOUT_W = 216;
const CALLOUT_H = 96;
const CALLOUT_GAP = 64;
const ANALYSIS_GAP = 56;
const ANALYSIS_STACK = 36;

interface Size {
  width: number;
  height: number;
}

interface ParentFrame {
  id: string;
  originX: number;
  originY: number;
}

interface PendingCallout {
  blockId: string;
  absY: number;
  label: string;
  snippet: string;
  startLine: number;
  startColumn: number;
  marker: SchemeMarker | null;
}

interface Ctx {
  byId: Map<string, ScratchBlock>;
  nodes: Node[];
  edges: Edge[];
  editMode: boolean;
  selectedBlockId: string | null | undefined;
  placed: Set<string>;
  markers: Map<string, SchemeMarker>;
  absoluteBoxes: Map<string, { x: number; y: number; w: number; h: number }>;
  parentStack: ParentFrame[];
  /** Правая граница основного графа (без внешних callout). */
  contentRight: number;
  pendingCallouts: PendingCallout[];
}

export function layoutModularFlow(
  scratch: ScratchProgram,
  selectedBlockId: string | null | undefined,
  editMode: boolean,
  markers: Map<string, SchemeMarker> = new Map(),
): { nodes: Node[]; edges: Edge[] } {
  const ctx: Ctx = {
    byId: new Map(scratch.blocks.map((block) => [block.id, block])),
    nodes: [],
    edges: [],
    editMode,
    selectedBlockId,
    placed: new Set(),
    markers,
    absoluteBoxes: new Map(),
    parentStack: [],
    contentRight: 56 + COL_W,
    pendingCallouts: [],
  };

  const roots =
    scratch.root_block_ids.length > 0
      ? scratch.root_block_ids
      : scratch.blocks.filter((block) => !block.parent_id).map((block) => block.id);

  let y = 40;
  for (const rootId of roots) {
    const root = ctx.byId.get(rootId);
    if (!root || ctx.placed.has(root.id)) {
      continue;
    }
    const size = layoutNode(ctx, root, 56, y);
    y += size.height + GAP_Y * 2;
    ctx.contentRight = Math.max(ctx.contentRight, 56 + size.width);
  }

  for (const block of scratch.blocks) {
    if (ctx.placed.has(block.id)) {
      continue;
    }
    const size = layoutNode(ctx, block, 56 + BRANCH_X, y);
    y += size.height + GAP_Y;
    ctx.contentRight = Math.max(ctx.contentRight, 56 + BRANCH_X + size.width);
  }

  placeDeferredCallouts(ctx);
  attachAnalysisAnchors(ctx);

  return { nodes: ctx.nodes, edges: ctx.edges };
}

function layoutNode(ctx: Ctx, block: ScratchBlock, x: number, y: number): Size {
  if (ctx.placed.has(block.id)) {
    return { width: 0, height: 0 };
  }
  if (block.kind === "if") {
    return layoutIf(ctx, block, x, y);
  }
  if (
    block.kind === "method" ||
    block.kind === "class" ||
    block.kind === "interface" ||
    block.kind === "enum" ||
    block.kind === "record"
  ) {
    return layoutMethod(ctx, block, x, y);
  }
  if (block.kind === "block") {
    return layoutTransparentBlock(ctx, block, x, y);
  }
  if (isStructureContainerKind(block.kind)) {
    return layoutStructureContainer(ctx, block, x, y);
  }
  if (block.kind === "call") {
    return layoutCall(ctx, block, x, y);
  }
  const card = estimateCardSize(block);
  pushCard(ctx, block, x, y, card);
  return continueNext(ctx, block, x, y, card);
}

/** Ширина/высота блока по краткой подписи (код - в описании, не на карточке). */
function estimateCardSize(block: ScratchBlock): Size {
  if (block.kind === "if") {
    return estimateDecisionSize(block);
  }
  const text = block.label.trim().slice(0, 48);
  const longest = text.length;
  const width = clamp(Math.max(COL_W * 0.72, 48 + longest * 7.2), MIN_CARD_W, Math.min(MAX_CARD_W, 280));
  let height = clamp(56 + Math.ceil(text.length / 28) * 14, MIN_CARD_H, 120);
  if (block.kind === "method" || block.kind === "class") {
    height = Math.max(height, METHOD_H);
  }
  return { width, height };
}

function estimateDecisionSize(block: ScratchBlock): Size {
  const text = block.label.trim().slice(0, 48);
  const longest = text.length;
  const side = clamp(Math.max(DECISION_H * 0.85, 72 + longest * 3.2), 110, 180);
  return { width: Math.round(side * 1.25), height: side };
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function layoutMethod(ctx: Ctx, block: ScratchBlock, x: number, y: number): Size {
  const self = estimateCardSize(block);
  pushCard(ctx, block, x, y, self);
  let height = self.height;
  let width = self.width;
  const bodyId = linkTarget(block, "body");
  if (bodyId) {
    const body = ctx.byId.get(bodyId);
    if (body && !ctx.placed.has(body.id)) {
      const bodySize = layoutNode(ctx, body, x, y + METHOD_H + GAP_Y);
      pushEdge(ctx, block.id, bodyId, "body", "out", false);
      height += GAP_Y + bodySize.height;
      width = Math.max(width, bodySize.width);
    } else if (bodyId) {
      pushEdge(ctx, block.id, bodyId, "body", "out", false);
    }
  }
  // Свободные шаблоны под методом (ещё без next/body-связей).
  const orphanSize = layoutOrphanChildren(ctx, block.id, x, y + height + GAP_Y);
  if (orphanSize.height > 0) {
    height += GAP_Y + orphanSize.height;
    width = Math.max(width, orphanSize.width);
  }
  return continueNext(ctx, block, x, y, { width, height });
}

/**
 * Структурный контейнер: шапка (условие/заголовок) + большое тело с подграфом.
 * Циклы, try/catch/finally, switch, else, case, synchronized, labeled.
 */
function layoutStructureContainer(ctx: Ctx, block: ScratchBlock, x: number, y: number): Size {
  ctx.placed.add(block.id);

  const contentX = PAD;
  const contentY = CONTAINER_HEADER + PAD;
  const groupIndex = ctx.nodes.length;

  ctx.nodes.push({
    id: block.id,
    type: "structureContainer",
    position: toLocal(ctx, x, y),
    data: nodeData(block, ctx),
    draggable: ctx.editMode,
    connectable: ctx.editMode,
    selected: ctx.selectedBlockId === block.id,
    style: {
      width: COL_W + PAD * 2,
      height: CONTAINER_HEADER + PAD * 2 + NODE_H,
      zIndex: 0,
    },
  });
  if (currentParent(ctx)) {
    ctx.nodes[groupIndex].parentId = currentParent(ctx)!.id;
  }

  ctx.parentStack.push({ id: block.id, originX: x, originY: y });

  let bodySize: Size = { width: COL_W, height: 0 };
  const bodyId = linkTarget(block, "body");
  if (bodyId) {
    const body = ctx.byId.get(bodyId);
    if (body && !ctx.placed.has(body.id)) {
      bodySize = layoutNode(ctx, body, x + contentX, y + contentY);
      pushEdge(ctx, block.id, bodyId, "body", "body", false);
    } else if (bodyId) {
      pushEdge(ctx, block.id, bodyId, "body", "body", false);
    }
  }

  // Элементы с parent_id = этот контейнер, ещё не связанные в body-цепочку.
  const orphanY =
    y + contentY + bodySize.height + (bodySize.height > 0 ? GAP_Y : 0);
  const orphanSize = layoutOrphanChildren(ctx, block.id, x + contentX, orphanY);
  if (orphanSize.height > 0) {
    bodySize = {
      width: Math.max(bodySize.width, orphanSize.width),
      height: bodySize.height + (bodySize.height > 0 ? GAP_Y : 0) + orphanSize.height,
    };
  }

  // Доп. ветки switch / try (children) - столбиком справа внутри контейнера.
  let sideCursorY = y + contentY;
  let sideWidth = 0;
  let sideHeight = 0;
  for (const link of block.links) {
    if (link.kind !== "children" && link.kind !== "catch" && link.kind !== "finally") {
      continue;
    }
    const child = ctx.byId.get(link.target_id);
    if (!child || ctx.placed.has(child.id)) {
      continue;
    }
    const childX = x + contentX + Math.max(bodySize.width, COL_W) + GAP_X;
    const childSize = layoutNode(ctx, child, childX, sideCursorY);
    pushEdge(ctx, block.id, child.id, link.kind, "else", true);
    sideWidth = Math.max(sideWidth, Math.max(bodySize.width, COL_W) + GAP_X + childSize.width);
    sideHeight = Math.max(sideHeight, sideCursorY - (y + contentY) + childSize.height);
    sideCursorY += childSize.height + GAP_Y;
  }

  ctx.parentStack.pop();

  const innerContentW = Math.max(COL_W, bodySize.width, sideWidth);
  const innerContentH = Math.max(bodySize.height, sideHeight, EMPTY_BODY_H);
  const innerW = innerContentW + PAD * 2;
  const innerH = CONTAINER_HEADER + PAD * 2 + innerContentH;

  ctx.nodes[groupIndex] = {
    ...ctx.nodes[groupIndex],
    style: {
      ...ctx.nodes[groupIndex].style,
      width: innerW,
      height: innerH,
    },
  };
  rememberAbsolute(ctx, block.id, x, y, innerW, innerH);
  ctx.contentRight = Math.max(ctx.contentRight, x + innerW);

  // После финального размера - жёсткие рамки: дети не выносятся за контейнер.
  lockChildrenToParent(ctx, block.id);

  return continueNext(ctx, block, x, y, { width: innerW, height: innerH });
}

/** Ограничивает перетаскивание детей пределами родителя. */
function lockChildrenToParent(ctx: Ctx, parentId: string): void {
  for (const node of ctx.nodes) {
    if (node.parentId === parentId) {
      node.extent = "parent";
      node.expandParent = true;
    }
  }
}

/** Дети контейнера/метода без входящих order-связей - кладём столбиком внутри. */
function layoutOrphanChildren(
  ctx: Ctx,
  parentId: string,
  x: number,
  startY: number,
): Size {
  const orphans = [...ctx.byId.values()].filter(
    (block) => block.parent_id === parentId && !ctx.placed.has(block.id),
  );
  if (orphans.length === 0) {
    return { width: 0, height: 0 };
  }
  let y = startY;
  let width = COL_W;
  let height = 0;
  for (const orphan of orphans) {
    if (ctx.placed.has(orphan.id)) {
      continue;
    }
    const size = layoutNode(ctx, orphan, x, y);
    width = Math.max(width, size.width);
    height = y - startY + size.height;
    y += size.height + GAP_Y;
  }
  return { width, height };
}

function layoutTransparentBlock(ctx: Ctx, block: ScratchBlock, x: number, y: number): Size {
  ctx.placed.add(block.id);
  const bodyId = linkTarget(block, "body");
  let size: Size = { width: COL_W, height: 0 };
  if (bodyId) {
    const body = ctx.byId.get(bodyId);
    if (body && !ctx.placed.has(body.id)) {
      size = layoutNode(ctx, body, x, y);
    }
  }
  const nextId = linkTarget(block, "next");
  if (nextId) {
    const next = ctx.byId.get(nextId);
    if (next && !ctx.placed.has(next.id)) {
      const gap = size.height > 0 ? GAP_Y : 0;
      const nextSize = layoutNode(ctx, next, x, y + size.height + gap);
      size = {
        width: Math.max(size.width, nextSize.width),
        height: size.height + gap + nextSize.height,
      };
    }
  }
  return size.height > 0 ? size : { width: COL_W, height: 0 };
}

function layoutIf(ctx: Ctx, block: ScratchBlock, x: number, y: number): Size {
  const self = estimateDecisionSize(block);
  pushCard(ctx, block, x, y, self);

  const bodyId = linkTarget(block, "body");
  const elseId = linkTarget(block, "else");
  const nextId = linkTarget(block, "next");
  const body = bodyId ? ctx.byId.get(bodyId) : undefined;
  const earlyExit = Boolean(body && isSideBranch(ctx, body));

  let downSize: Size = { width: self.width, height: 0 };
  let sideSize: Size = { width: 0, height: 0 };
  let sideY = y;

  if (body && earlyExit) {
    sideSize = layoutNode(ctx, body, x + Math.max(BRANCH_X, self.width + GAP_X), sideY);
    pushEdge(ctx, block.id, body.id, "body", "else", true, uiText.graphBranchYes);
    sideY += sideSize.height + GAP_Y;
  } else if (body && !ctx.placed.has(body.id)) {
    downSize = layoutNode(ctx, body, x, y + self.height + GAP_Y);
    pushEdge(ctx, block.id, body.id, "body", "body", false, uiText.graphBranchYes);
  }

  if (elseId) {
    const elseBlock = ctx.byId.get(elseId);
    if (elseBlock && !ctx.placed.has(elseBlock.id)) {
      const elseSize = layoutNode(
        ctx,
        elseBlock,
        x + Math.max(BRANCH_X, self.width + GAP_X),
        sideY,
      );
      pushEdge(ctx, block.id, elseId, "else", "else", true, uiText.graphBranchNo);
      sideSize = {
        width: Math.max(sideSize.width, elseSize.width),
        height: Math.max(sideSize.height, sideY - y + elseSize.height),
      };
    }
  }

  let nextSize: Size = { width: 0, height: 0 };
  const below =
    y + self.height + (downSize.height > 0 ? GAP_Y + downSize.height : 0) + GAP_Y;
  if (nextId && shouldFollowNextInside(ctx, block, nextId)) {
    const next = ctx.byId.get(nextId);
    if (next && !ctx.placed.has(next.id)) {
      nextSize = layoutNode(ctx, next, x, below);
      pushEdge(
        ctx,
        block.id,
        nextId,
        "next",
        "out",
        false,
        earlyExit && !elseId ? uiText.graphBranchNo : undefined,
      );
    } else if (next) {
      pushEdge(
        ctx,
        block.id,
        nextId,
        "next",
        "out",
        false,
        earlyExit && !elseId ? uiText.graphBranchNo : undefined,
      );
    }
  }

  // Высота учитывает и боковую ветку, и продолжение вниз - без пересечения next с side.
  const branchOffset = Math.max(BRANCH_X, self.width + GAP_X);
  const mainH =
    self.height +
    (downSize.height > 0 ? GAP_Y + downSize.height : 0) +
    (nextSize.height > 0 ? GAP_Y + nextSize.height : 0);
  const height = Math.max(mainH, sideSize.height > 0 ? sideSize.height : self.height, self.height);
  const width = Math.max(
    self.width,
    downSize.width,
    nextSize.width,
    sideSize.width > 0 ? branchOffset + sideSize.width : self.width,
  );
  return { width, height };
}

function isSideBranch(ctx: Ctx, block: ScratchBlock): boolean {
  if (isExitKind(block.kind)) {
    return true;
  }
  if (
    isStructureContainerKind(block.kind) ||
    block.kind === "if" ||
    block.kind === "method" ||
    block.kind === "block"
  ) {
    return false;
  }
  let current: ScratchBlock | undefined = block;
  let steps = 0;
  while (current && steps < 3) {
    if (isExitKind(current.kind)) {
      return true;
    }
    if (linkTarget(current, "body") || linkTarget(current, "else")) {
      return false;
    }
    const nextId = linkTarget(current, "next");
    if (!nextId) {
      return false;
    }
    current = ctx.byId.get(nextId);
    steps += 1;
  }
  return false;
}

function layoutCall(ctx: Ctx, block: ScratchBlock, x: number, y: number): Size {
  const self = estimateCardSize(block);
  pushCard(ctx, block, x, y, self);
  // Callout выносится позже в отдельную колонку справа - без пересечения с ветками.
  ctx.pendingCallouts.push({
    blockId: block.id,
    absY: y,
    label: block.label,
    snippet: block.source_snippet ?? "",
    startLine: block.span.start_line,
    startColumn: block.span.start_column,
    marker: ctx.markers.get(block.id) ?? null,
  });
  return continueNext(ctx, block, x, y, self);
}

function placeDeferredCallouts(ctx: Ctx): void {
  if (ctx.pendingCallouts.length === 0) {
    return;
  }
  const colX = ctx.contentRight + CALLOUT_GAP;
  const sorted = [...ctx.pendingCallouts].sort((a, b) => a.absY - b.absY);
  let cursorY = sorted[0]?.absY ?? 40;
  for (const item of sorted) {
    const calloutId = `callout:${item.blockId}`;
    if (ctx.nodes.some((node) => node.id === calloutId)) {
      continue;
    }
    const y = Math.max(item.absY, cursorY);
    ctx.nodes.push({
      id: calloutId,
      type: "modularCallout",
      position: { x: colX, y },
      data: {
        label: item.label,
        kind: "call",
        color: schemeColors.callout,
        startLine: item.startLine,
        startColumn: item.startColumn,
        editable: false,
        connectable: false,
        snippet: item.snippet,
        title: uiText.graphExternalCall,
        marker: item.marker,
        icon: "callout",
      } satisfies ScratchNodeData,
      draggable: false,
      connectable: false,
      selectable: true,
      style: { width: CALLOUT_W, zIndex: 3 },
    });
    ctx.edges.push({
      id: `${item.blockId}->${calloutId}:callout`,
      source: item.blockId,
      target: calloutId,
      sourceHandle: "callout",
      targetHandle: "in",
      type: "schemeCallout",
      animated: false,
      deletable: false,
      data: { sideways: true },
    });
    rememberAbsolute(ctx, calloutId, colX, y, CALLOUT_W, CALLOUT_H);
    cursorY = y + CALLOUT_H + GAP_Y;
  }
  ctx.contentRight = Math.max(ctx.contentRight, colX + CALLOUT_W);
}

function continueNext(
  ctx: Ctx,
  block: ScratchBlock,
  x: number,
  y: number,
  self: Size,
): Size {
  const nextId = linkTarget(block, "next");
  if (!nextId) {
    return self;
  }
  if (!shouldFollowNextInside(ctx, block, nextId)) {
    // Внешний выход контейнера - только через out родителя, без возврата внутрь.
    return self;
  }
  const next = ctx.byId.get(nextId);
  if (!next) {
    return self;
  }
  if (ctx.placed.has(next.id)) {
    pushEdge(ctx, block.id, nextId, "next", "out", false);
    return self;
  }
  const nextSize = layoutNode(ctx, next, x, y + self.height + GAP_Y);
  pushEdge(ctx, block.id, nextId, "next", "out", false);
  return {
    width: Math.max(self.width, nextSize.width),
    height: self.height + GAP_Y + nextSize.height,
  };
}

/**
 * Внутри цикла/контейнера next не должен уводить поток наружу:
 * иначе стрелка из внешнего выхода визуально возвращается в тело.
 */
function shouldFollowNextInside(ctx: Ctx, block: ScratchBlock, nextId: string): boolean {
  const parent = currentParent(ctx);
  if (!parent) {
    return true;
  }
  const container = ctx.byId.get(parent.id);
  if (container && linkTarget(container, "next") === nextId) {
    return false;
  }
  const next = ctx.byId.get(nextId);
  if (!next) {
    return false;
  }
  if (next.parent_id && next.parent_id !== parent.id) {
    return false;
  }
  return true;
}

function pushCard(ctx: Ctx, block: ScratchBlock, x: number, y: number, size: Size): void {
  ctx.placed.add(block.id);
  const parent = currentParent(ctx);
  const node: Node = {
    id: block.id,
    type: scratchFlowNodeType(block.kind),
    position: toLocal(ctx, x, y),
    data: nodeData(block, ctx),
    draggable: ctx.editMode,
    connectable: ctx.editMode,
    selected: ctx.selectedBlockId === block.id,
    style: {
      width: size.width,
      height: size.height,
      minHeight: size.height,
      zIndex: 2,
      ...(ctx.selectedBlockId === block.id
        ? { outline: "2px solid #fde047", outlineOffset: 2 }
        : {}),
    },
  };
  if (parent) {
    node.parentId = parent.id;
    // extent:parent выставляется после финального размера контейнера.
  }
  ctx.nodes.push(node);
  rememberAbsolute(ctx, block.id, x, y, size.width, size.height);
  ctx.contentRight = Math.max(ctx.contentRight, x + size.width);
}

function pushEdge(
  ctx: Ctx,
  source: string,
  target: string,
  kind: string,
  sourceHandle: string,
  sideways: boolean,
  label?: string,
): void {
  const id = `${source}->${target}:${kind}`;
  if (ctx.edges.some((edge) => edge.id === id)) {
    return;
  }
  let edgeLabel = label;
  if (!edgeLabel && kind === "else") {
    edgeLabel = uiText.graphBranchNo;
  }
  // body и всё под parentStack - внутренний поток; next контейнера после pop - внешний.
  const flowScope: "inner" | "outer" =
    kind === "body" || kind === "catch" || kind === "finally" || kind === "children"
      ? "inner"
      : currentParent(ctx)
        ? "inner"
        : "outer";
  const stroke =
    flowScope === "inner"
      ? sideways
        ? schemeColors.edgeBranch
        : schemeColors.edgeInner
      : sideways
        ? schemeColors.edgeBranch
        : schemeColors.edgeMain;
  ctx.edges.push({
    id,
    source,
    target,
    sourceHandle,
    targetHandle: "in",
    label: edgeLabel,
    animated: false,
    selectable: true,
    focusable: true,
    deletable: ctx.editMode && !id.includes("callout") && !id.includes("analysis"),
    type: "schemeFlow",
    data: { sideways, linkKind: kind, flowScope },
    style: {
      stroke,
      strokeWidth: flowScope === "inner" ? 2 : 2.4,
      ...(flowScope === "inner" && !sideways ? { strokeDasharray: "0" } : {}),
    },
  });
}

function attachAnalysisAnchors(ctx: Ctx): void {
  const right = ctx.contentRight + ANALYSIS_GAP;
  const entries = [...ctx.markers.entries()]
    .filter(([blockId]) => ctx.absoluteBoxes.has(blockId))
    .sort((a, b) => {
      const ya = ctx.absoluteBoxes.get(a[0])?.y ?? 0;
      const yb = ctx.absoluteBoxes.get(b[0])?.y ?? 0;
      return ya - yb;
    });

  let cursorY = entries[0] ? (ctx.absoluteBoxes.get(entries[0][0])?.y ?? 40) : 40;
  for (const [blockId, marker] of entries) {
    const box = ctx.absoluteBoxes.get(blockId);
    if (!box) {
      continue;
    }
    const anchorId = `analysis:${blockId}`;
    if (ctx.nodes.some((node) => node.id === anchorId)) {
      continue;
    }
    const y = Math.max(box.y + 12, cursorY);
    ctx.nodes.push({
      id: anchorId,
      type: "modularAnalysis",
      position: { x: right, y },
      data: {
        label: uiText.graphAnalysisLink,
        kind: "analysis",
        color: schemeColors.analysis,
        startLine: null,
        startColumn: null,
        editable: false,
        connectable: false,
        title: uiText.graphAnalysisLink,
        marker,
      } satisfies ScratchNodeData,
      draggable: false,
      connectable: false,
      selectable: false,
      style: { width: 28, height: 28, zIndex: 4 },
    });
    ctx.edges.push({
      id: `${blockId}->${anchorId}:analysis`,
      source: blockId,
      target: anchorId,
      sourceHandle: "callout",
      targetHandle: "in",
      type: "schemeAnalysis",
      deletable: false,
      data: { severity: marker.severity },
    });
    cursorY = y + ANALYSIS_STACK;
  }
}

function currentParent(ctx: Ctx): ParentFrame | null {
  return ctx.parentStack.length > 0 ? ctx.parentStack[ctx.parentStack.length - 1] : null;
}

function toLocal(ctx: Ctx, absX: number, absY: number): { x: number; y: number } {
  const parent = currentParent(ctx);
  if (!parent) {
    return { x: absX, y: absY };
  }
  return { x: absX - parent.originX, y: absY - parent.originY };
}

function rememberAbsolute(
  ctx: Ctx,
  id: string,
  x: number,
  y: number,
  w: number,
  h: number,
): void {
  ctx.absoluteBoxes.set(id, { x, y, w, h });
}

function linkTarget(block: ScratchBlock, kind: string): string | undefined {
  return block.links.find((link) => link.kind === kind)?.target_id;
}

function nodeData(block: ScratchBlock, ctx: Ctx): ScratchNodeData {
  const title = isStructureContainerKind(block.kind)
    ? containerTitle(block.kind)
    : roleTitle(block.kind);
  const { accent } = accentForKind(block.kind);
  return {
    label: block.label,
    kind: block.kind,
    color: accent,
    startLine: block.span.start_line,
    startColumn: block.span.start_column,
    editable: block.editable !== false,
    connectable: ctx.editMode,
    snippet: block.source_snippet ?? "",
    title,
    isContainer: isStructureContainerKind(block.kind),
    marker: ctx.markers.get(block.id) ?? null,
    icon:
      block.kind === "method" || block.kind === "class"
        ? "method"
        : block.kind === "variable" || block.kind === "parameter"
          ? "variable"
          : block.kind === "call"
            ? "callout"
            : block.kind === "return"
              ? "return"
              : block.kind === "continue" || block.kind === "break"
                ? "continue"
                : "operation",
  };
}
