"use client";

import {
  Background,
  ReactFlow,
  ReactFlowProvider,
  applyEdgeChanges,
  applyNodeChanges,
  useReactFlow,
  type Connection,
  type Edge,
  type EdgeChange,
  type Node,
  type NodeChange,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useEffect, useMemo, useRef, useState, type DragEvent } from "react";

import { schemeEdgeTypes } from "@/components/graph/schemeEdges";
import { scratchNodeTypes, type ScratchNodeData } from "@/components/graph/scratchNodes";
import { uiText } from "@/shared/i18n/ru";
import { layoutModularFlow } from "@/shared/lib/modularLayout";
import {
  BLOCK_PALETTE,
  canConnectBlocks,
  canDeleteBlock,
  connectBlocks,
  deleteBlock,
  disconnectBlocks,
  insertBlock,
  isCompositeHostKind,
  moveBlockAmongSiblings,
  schemeStructureKey,
  updateBlockContent,
  type InsertableBlockKind,
  type InsertMode,
} from "@/shared/lib/schemeEdit";
import { isLoopKind, type SchemeMarker } from "@/shared/lib/schemeTheme";
import type { ScratchProgram } from "@/shared/types/workspace";

interface GraphWorkspaceProps {
  scratch: ScratchProgram | null;
  stale: boolean;
  selectedBlockId?: string | null;
  editMode?: boolean;
  schemeDirty?: boolean;
  saveBusy?: boolean;
  collapsed?: boolean;
  fullscreen?: boolean;
  compact?: boolean;
  markers?: Map<string, SchemeMarker>;
  onSelectNode?: (
    nodeId: string | null,
    startLine: number | null,
    startColumn: number | null,
  ) => void;
  onToggleEdit?: () => void;
  onScratchChange?: (scratch: ScratchProgram) => void;
  onSaveScheme?: () => void;
  onToggleCollapsed?: () => void;
  onToggleFullscreen?: () => void;
  onCreateBlankScheme?: () => void;
  canUndo?: boolean;
  onUndo?: () => void;
  onExitWithoutSave?: () => void;
}

function linkKindFromHandle(handleId: string | null | undefined): string {
  if (handleId === "else" || handleId === "body") {
    return handleId;
  }
  return "next";
}

function linkKindFromEdge(edge: Edge): string {
  const fromData = (edge.data as { linkKind?: string } | undefined)?.linkKind;
  if (fromData) {
    return fromData;
  }
  return linkKindFromHandle(edge.sourceHandle);
}

function edgeLabelForKind(kind: string): string | undefined {
  if (kind === "else") {
    return uiText.graphBranchNo;
  }
  if (kind === "body") {
    return uiText.graphBranchYes;
  }
  return undefined;
}

function applySelection(
  nodes: Node[],
  edges: Edge[],
  selectedBlockId: string | null | undefined,
  selectedEdgeId: string | null,
): { nodes: Node[]; edges: Edge[] } {
  return {
    nodes: nodes.map((node) => ({
      ...node,
      selected: node.id === selectedBlockId,
      style: {
        ...node.style,
        ...(node.id === selectedBlockId
          ? { outline: "2px solid #fde047", outlineOffset: 2 }
          : { outline: undefined, outlineOffset: undefined }),
      },
    })),
    edges: edges.map((edge) => ({
      ...edge,
      selected: edge.id === selectedEdgeId,
    })),
  };
}

function GraphCanvas({
  scratch,
  stale,
  selectedBlockId,
  editMode = false,
  schemeDirty = false,
  markers,
  onSelectNode,
  onScratchChange,
  onCreateBlankScheme,
}: GraphWorkspaceProps) {
  const { fitView, screenToFlowPosition } = useReactFlow();
  const structureKey = useMemo(
    () => (scratch ? `${schemeStructureKey(scratch)}|edit:${editMode}` : ""),
    [scratch, editMode],
  );
  const markersKey = useMemo(() => {
    if (!markers || markers.size === 0) {
      return "";
    }
    return [...markers.entries()]
      .map(([id, marker]) => `${id}:${marker.severity}:${marker.count}`)
      .join("|");
  }, [markers]);

  const laidOut = useMemo(() => {
    if (!scratch) {
      return { nodes: [] as Node[], edges: [] as Edge[] };
    }
    // Selection не участвует в раскладке - иначе клик сбрасывает позиции.
    return layoutModularFlow(scratch, null, editMode, markers ?? new Map());
    // eslint-disable-next-line react-hooks/exhaustive-deps -- ключи стабилизируют Map/объект
  }, [structureKey, markersKey, editMode]);

  const [nodes, setNodes] = useState<Node[]>(laidOut.nodes);
  const [edges, setEdges] = useState<Edge[]>(laidOut.edges);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [hintsHidden, setHintsHidden] = useState(true);
  const [paletteHidden, setPaletteHidden] = useState(true);
  const [editorHidden, setEditorHidden] = useState(true);
  /** Ручные размеры блоков (не сбрасываются при клике, переживают relayout). */
  const sizeOverridesRef = useRef<Record<string, { width: number; height: number }>>({});
  /** Позиции после drop с палитры (свободная вставка без автосвязей). */
  const positionOverridesRef = useRef<Record<string, { x: number; y: number }>>({});
  const lastFitKey = useRef<string>("");

  function applySizeOverrides(list: Node[]): Node[] {
    const overrides = sizeOverridesRef.current;
    return list.map((node) => {
      const size = overrides[node.id];
      if (!size) {
        return node;
      }
      return {
        ...node,
        style: {
          ...node.style,
          width: size.width,
          height: size.height,
          minHeight: size.height,
        },
      };
    });
  }

  function applyPositionOverrides(list: Node[]): Node[] {
    const overrides = positionOverridesRef.current;
    if (Object.keys(overrides).length === 0) {
      return list;
    }
    return list.map((node) => {
      const position = overrides[node.id];
      if (!position) {
        return node;
      }
      return { ...node, position: { x: position.x, y: position.y } };
    });
  }

  // Пересборка только при изменении структуры, не при клике/выделении.
  useEffect(() => {
    const next = applySelection(
      applyPositionOverrides(applySizeOverrides(laidOut.nodes)),
      laidOut.edges,
      selectedBlockId,
      selectedEdgeId,
    );
    setNodes(next.nodes);
    setEdges(next.edges);
    // selected* нарочно не в deps: иначе клик откатывает drag-позиции.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [laidOut.nodes, laidOut.edges]);

  useEffect(() => {
    setNodes((current) =>
      current.map((node) => ({
        ...node,
        selected: node.id === selectedBlockId,
        style: {
          ...node.style,
          ...(node.id === selectedBlockId
            ? { outline: "2px solid #fde047", outlineOffset: 2 }
            : { outline: undefined, outlineOffset: undefined }),
        },
      })),
    );
  }, [selectedBlockId]);

  useEffect(() => {
    setEdges((current) =>
      current.map((edge) => ({
        ...edge,
        selected: edge.id === selectedEdgeId,
      })),
    );
  }, [selectedEdgeId]);

  useEffect(() => {
    if (!structureKey || structureKey === lastFitKey.current) {
      return;
    }
    lastFitKey.current = structureKey;
    const timer = window.setTimeout(() => {
      void fitView({ padding: 0.18, duration: 200 });
    }, 40);
    return () => window.clearTimeout(timer);
  }, [structureKey, fitView]);

  // В режиме правки всплывающие панели свёрнуты, пока пользователь их не откроет.
  useEffect(() => {
    if (editMode) {
      setHintsHidden(true);
      setPaletteHidden(true);
      setEditorHidden(true);
    }
  }, [editMode]);

  const empty = !scratch || scratch.blocks.length === 0;
  const moduleCount = scratch?.modules?.length ?? 0;
  const selectedBlock = scratch?.blocks.find((block) => block.id === selectedBlockId) ?? null;
  const selectedEdge = edges.find((edge) => edge.id === selectedEdgeId) ?? null;
  const canReorder = Boolean(
    editMode && selectedBlock && selectedBlock.editable !== false && onScratchChange && scratch,
  );

  function onNodesChange(changes: NodeChange[]) {
    for (const change of changes) {
      if (change.type === "dimensions" && change.dimensions) {
        sizeOverridesRef.current[change.id] = {
          width: change.dimensions.width,
          height: change.dimensions.height,
        };
      }
      if (change.type === "position" && change.position && change.dragging === false) {
        positionOverridesRef.current[change.id] = {
          x: change.position.x,
          y: change.position.y,
        };
      }
      if (change.type === "remove") {
        delete sizeOverridesRef.current[change.id];
        delete positionOverridesRef.current[change.id];
      }
    }
    // Позиции/выделение на холсте не должны пересобирать программу.
    const structuralRemove = changes.some((change) => change.type === "remove");
    if (!scratch || !onScratchChange || !structuralRemove) {
      setNodes((current) => applyNodeChanges(changes, current));
      return;
    }
    let nextProgram = scratch;
    let removed = false;
    for (const change of changes) {
      if (change.type === "remove" && canDeleteBlock(nextProgram, change.id)) {
        nextProgram = deleteBlock(nextProgram, change.id);
        removed = true;
      }
    }
    setNodes((current) => applyNodeChanges(changes, current));
    if (removed) {
      onScratchChange(nextProgram);
    }
  }

  function onEdgesChange(changes: EdgeChange[]) {
    if (!scratch || !onScratchChange) {
      setEdges((current) => applyEdgeChanges(changes, current));
      return;
    }
    let nextProgram = scratch;
    let changed = false;
    for (const change of changes) {
      if (change.type === "remove") {
        const edge = edges.find((item) => item.id === change.id);
        if (edge && edge.deletable !== false) {
          nextProgram = disconnectBlocks(
            nextProgram,
            edge.source,
            edge.target,
            linkKindFromEdge(edge),
          );
          changed = true;
          if (selectedEdgeId === change.id) {
            setSelectedEdgeId(null);
          }
        }
      }
    }
    setEdges((current) => applyEdgeChanges(changes, current));
    if (changed) {
      onScratchChange(nextProgram);
    }
  }

  function onConnect(connection: Connection) {
    if (!scratch || !onScratchChange || !connection.source || !connection.target) {
      return;
    }
    if (
      connection.source.startsWith("callout:") ||
      connection.source.startsWith("analysis:") ||
      connection.target.startsWith("callout:") ||
      connection.target.startsWith("analysis:")
    ) {
      return;
    }
    const kind = linkKindFromHandle(connection.sourceHandle);
    if (!canConnectBlocks(scratch, connection.source, connection.target, kind)) {
      return;
    }
    onScratchChange(connectBlocks(scratch, connection.source, connection.target, kind));
  }

  function isValidConnection(connection: Connection | { source: string | null; target: string | null; sourceHandle?: string | null }) {
    if (!scratch || !connection.source || !connection.target) {
      return false;
    }
    if (
      connection.source.startsWith("callout:") ||
      connection.source.startsWith("analysis:") ||
      connection.target.startsWith("callout:") ||
      connection.target.startsWith("analysis:")
    ) {
      return false;
    }
    return canConnectBlocks(
      scratch,
      connection.source,
      connection.target,
      linkKindFromHandle(connection.sourceHandle),
    );
  }

  function commitBlockFields(nextLabel: string, nextSnippet: string) {
    if (!scratch || !selectedBlock || !onScratchChange) {
      return;
    }
    onScratchChange(
      updateBlockContent(scratch, selectedBlock.id, {
        label: nextLabel,
        source_snippet: nextSnippet,
      }),
    );
  }

  function reorder(direction: "up" | "down") {
    if (!scratch || !selectedBlockId || !onScratchChange) {
      return;
    }
    onScratchChange(moveBlockAmongSiblings(scratch, selectedBlockId, direction));
  }

  function removeSelectedBlock() {
    if (!scratch || !selectedBlockId || !onScratchChange) {
      return;
    }
    if (!canDeleteBlock(scratch, selectedBlockId)) {
      return;
    }
    onScratchChange(deleteBlock(scratch, selectedBlockId));
  }

  function removeSelectedEdge() {
    if (!scratch || !onScratchChange || !selectedEdge) {
      return;
    }
    if (selectedEdge.deletable === false) {
      return;
    }
    onScratchChange(
      disconnectBlocks(
        scratch,
        selectedEdge.source,
        selectedEdge.target,
        linkKindFromEdge(selectedEdge),
      ),
    );
    setSelectedEdgeId(null);
  }

  function addBlock(
    kind: InsertableBlockKind,
    mode: InsertMode = "free",
    dropPosition?: { x: number; y: number },
  ) {
    if (!scratch || !onScratchChange) {
      return;
    }
    const selected = selectedBlockId
      ? scratch.blocks.find((block) => block.id === selectedBlockId)
      : null;
    // По умолчанию - свободный шаблон, не зависит от выделения и без автосвязей.
    if (mode === "free") {
      const next = insertBlock(scratch, kind, { free: true });
      if (dropPosition) {
        const added = next.blocks.find(
          (block) => !scratch.blocks.some((existing) => existing.id === block.id),
        );
        if (added) {
          positionOverridesRef.current[added.id] = dropPosition;
        }
      }
      onScratchChange(next);
      return;
    }
    if (mode === "body") {
      // В тело: выбранный контейнер/цикл, родитель выделенного узла внутри цикла, иначе последний контейнер.
      let host =
        selected && (isCompositeHostKind(selected.kind) || isLoopKind(selected.kind))
          ? selected
          : null;
      if (!host && selected?.parent_id) {
        const parent = scratch.blocks.find((block) => block.id === selected.parent_id);
        if (parent && (isCompositeHostKind(parent.kind) || isLoopKind(parent.kind))) {
          host = parent;
        }
      }
      if (!host) {
        host =
          [...scratch.blocks]
            .reverse()
            .find((block) => isCompositeHostKind(block.kind) || isLoopKind(block.kind)) ?? null;
      }
      if (host) {
        onScratchChange(insertBlock(scratch, kind, { intoBodyOfId: host.id }));
      } else {
        onScratchChange(insertBlock(scratch, kind, { free: true }));
      }
      return;
    }
    if (selected) {
      onScratchChange(insertBlock(scratch, kind, { afterId: selected.id }));
      return;
    }
    onScratchChange(insertBlock(scratch, kind, { free: true }));
  }

  function onPaletteDragStart(event: DragEvent, kind: InsertableBlockKind) {
    event.dataTransfer.setData("application/jb-block-kind", kind);
    event.dataTransfer.effectAllowed = "copy";
  }

  function onCanvasDragOver(event: DragEvent) {
    if (!editMode || !event.dataTransfer.types.includes("application/jb-block-kind")) {
      return;
    }
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
  }

  function onCanvasDrop(event: DragEvent) {
    if (!editMode || !scratch || !onScratchChange) {
      return;
    }
    const kind = event.dataTransfer.getData("application/jb-block-kind") as InsertableBlockKind;
    if (!kind || !BLOCK_PALETTE.some((item) => item.kind === kind)) {
      return;
    }
    event.preventDefault();
    const position = screenToFlowPosition({ x: event.clientX, y: event.clientY });
    addBlock(kind, "free", position);
  }

  const canDeleteSelected = Boolean(
    editMode && selectedBlockId && scratch && canDeleteBlock(scratch, selectedBlockId),
  );

  return (
    <div
      className="relative h-full min-h-0 w-full"
      onDragOver={editMode ? onCanvasDragOver : undefined}
      onDrop={editMode ? onCanvasDrop : undefined}
    >
      <ReactFlow
        nodes={nodes.map((node) => ({
          ...node,
          deletable: editMode && scratch != null && canDeleteBlock(scratch, node.id),
        }))}
        edges={edges.map((edge) => ({
          ...edge,
          deletable: editMode && edge.deletable !== false,
          selectable: true,
          label:
            edge.type === "schemeFlow"
              ? edge.label ?? edgeLabelForKind(linkKindFromEdge(edge))
              : edge.label,
        }))}
        nodeTypes={scratchNodeTypes}
        edgeTypes={schemeEdgeTypes}
        proOptions={{ hideAttribution: true }}
        nodesDraggable={editMode}
        nodesConnectable={editMode}
        edgesReconnectable={editMode}
        elementsSelectable={!empty}
        edgesFocusable
        deleteKeyCode={editMode ? ["Backspace", "Delete"] : null}
        onNodesChange={onNodesChange}
        onEdgesChange={editMode ? onEdgesChange : undefined}
        onConnect={editMode ? onConnect : undefined}
        isValidConnection={editMode ? isValidConnection : undefined}
        onNodeClick={(_event, node) => {
          setSelectedEdgeId(null);
          if (node.id.startsWith("analysis:") || node.id.startsWith("callout:")) {
            const sourceId = node.id.slice(node.id.indexOf(":") + 1);
            const source = nodes.find((item) => item.id === sourceId);
            const data = (source?.data ?? node.data) as ScratchNodeData;
            onSelectNode?.(sourceId, data.startLine, data.startColumn);
            return;
          }
          const data = node.data as ScratchNodeData;
          onSelectNode?.(node.id, data.startLine, data.startColumn);
        }}
        onEdgeClick={(_event, edge) => {
          if (!editMode || edge.deletable === false) {
            return;
          }
          setSelectedEdgeId(edge.id);
          onSelectNode?.(null, null, null);
        }}
        onPaneClick={() => {
          setSelectedEdgeId(null);
        }}
        className="scheme-canvas"
      >
        <Background color="#334155" gap={18} size={1} />
      </ReactFlow>

      {empty ? (
        <div className="absolute inset-0 z-10 flex items-center justify-center p-6">
          <div className="max-w-md rounded border border-slate-600/80 bg-slate-950/95 px-4 py-4 text-center shadow-xl">
            <p className="text-xs leading-relaxed text-slate-300">{uiText.graphEmpty}</p>
            <p className="mt-2 text-[11px] leading-relaxed text-slate-500">
              {uiText.graphCreateBlankHint}
            </p>
            {onCreateBlankScheme ? (
              <button
                type="button"
                className="mt-3 rounded border border-violet-700 bg-violet-950/50 px-3 py-1.5 text-[11px] font-medium text-violet-100 hover:bg-violet-900/50"
                onClick={onCreateBlankScheme}
              >
                {uiText.graphCreateBlank}
              </button>
            ) : null}
          </div>
        </div>
      ) : null}

      <div className="pointer-events-none absolute inset-x-0 top-0 z-20 flex items-start justify-between gap-2 p-2">
        <div className="pointer-events-auto flex max-h-[40%] max-w-[48%] flex-col gap-1 overflow-auto">
          <div className="flex flex-wrap items-center gap-1">
            <button
              type="button"
              title={hintsHidden ? uiText.graphHintsShow : uiText.graphHintsHide}
              aria-label={hintsHidden ? uiText.graphHintsShow : uiText.graphHintsHide}
              className="rounded border border-slate-600 bg-slate-950/90 px-2 py-0.5 text-[10px] font-semibold text-slate-200 hover:bg-slate-800"
              onClick={() => setHintsHidden((value) => !value)}
            >
              {uiText.collapseToggle}
            </button>
            <button
              type="button"
              className="rounded border border-slate-600 bg-slate-950/90 px-2 py-0.5 text-[10px] text-slate-200 hover:bg-slate-800"
              onClick={() => void fitView({ padding: 0.18, duration: 200 })}
            >
              {uiText.graphFitView}
            </button>
          </div>
          {!hintsHidden ? (
            <div className="flex flex-wrap gap-1">
              {scratch?.method_name ? (
                <div className="rounded border border-slate-600 bg-slate-950/90 px-2 py-1 text-[10px] text-slate-200">
                  {uiText.graphMethod}: {scratch.method_name}
                </div>
              ) : null}
              {moduleCount > 0 ? (
                <div className="rounded border border-slate-600 bg-slate-950/90 px-2 py-1 text-[10px] text-slate-200">
                  {uiText.graphModules}: {moduleCount}
                </div>
              ) : null}
              {schemeDirty ? (
                <div className="rounded border border-amber-700 bg-amber-950/90 px-2 py-1 text-[10px] text-amber-200">
                  {uiText.graphDirty}
                </div>
              ) : null}
              {editMode ? (
                <div className="max-w-xs rounded border border-sky-800 bg-sky-950/90 px-2 py-1 text-[10px] text-sky-100">
                  {uiText.graphConnectHint}
                </div>
              ) : null}
              {stale ? (
                <div className="rounded border border-amber-700 bg-amber-950/90 px-2 py-1 text-[10px] text-amber-200">
                  {uiText.graphStale}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>

        <div className="pointer-events-auto flex max-h-[72%] flex-col items-end gap-1">
          {editMode ? (
            <>
              <button
                type="button"
                title={paletteHidden ? uiText.graphPaletteShow : uiText.graphPaletteHide}
                aria-label={paletteHidden ? uiText.graphPaletteShow : uiText.graphPaletteHide}
                className="rounded border border-slate-600 bg-slate-950/90 px-2 py-0.5 text-[10px] font-semibold text-slate-200 hover:bg-slate-800"
                onClick={() => setPaletteHidden((value) => !value)}
              >
                {uiText.collapseToggle}
              </button>
              {!paletteHidden ? (
                <div className="flex w-52 max-h-[min(460px,62vh)] flex-col overflow-hidden rounded border border-slate-600 bg-slate-950/95 shadow-lg">
                  <div className="shrink-0 border-b border-slate-800 px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                    {uiText.graphPaletteTitle}
                  </div>
                  <p className="shrink-0 px-2 py-1 text-[9px] leading-snug text-slate-500">
                    {uiText.graphPaletteDragHint}
                  </p>
                  <div className="min-h-0 flex-1 overflow-y-auto px-1.5 pb-1.5">
                    <div className="flex flex-col gap-0.5">
                      {BLOCK_PALETTE.map((item) => (
                        <div key={item.kind} className="flex gap-0.5">
                          <button
                            type="button"
                            draggable
                            title={`${item.title}: ${uiText.graphInsertFree}`}
                            className="min-w-0 flex-1 cursor-grab truncate rounded border border-slate-700 px-1.5 py-0.5 text-left text-[10px] text-slate-100 hover:bg-slate-800 active:cursor-grabbing"
                            style={{ borderLeftColor: item.color, borderLeftWidth: 3 }}
                            onDragStart={(event) => onPaletteDragStart(event, item.kind)}
                            onClick={() => addBlock(item.kind, "free")}
                          >
                            {item.title}
                          </button>
                          <button
                            type="button"
                            title={uiText.graphInsertIntoBody}
                            className="rounded border border-slate-700 px-1 py-0.5 text-[9px] text-slate-300 hover:bg-slate-800"
                            onClick={() => addBlock(item.kind, "body")}
                          >
                            {uiText.graphInsertIntoBody}
                          </button>
                          <button
                            type="button"
                            title={uiText.graphInsertAfter}
                            className="rounded border border-slate-700 px-1 py-0.5 text-[9px] text-slate-400 hover:bg-slate-800"
                            onClick={() => addBlock(item.kind, "after")}
                          >
                            ↓
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : null}
            </>
          ) : null}
        </div>
      </div>

      {editMode && selectedEdge ? (
        <div className="absolute bottom-2 right-2 z-20 max-w-xs rounded border border-sky-800 bg-slate-950/95 p-2 shadow-lg">
          <div className="mb-1 text-[10px] uppercase tracking-wide text-slate-500">
            {uiText.graphEdgeSelected}
          </div>
          <div className="mb-2 text-[11px] text-slate-300">
            {selectedEdge.source} → {selectedEdge.target}
            {selectedEdge.label ? ` (${String(selectedEdge.label)})` : ""}
          </div>
          <button
            type="button"
            className="rounded border border-red-800 px-2 py-0.5 text-[10px] text-red-200 hover:bg-red-950/50"
            onClick={removeSelectedEdge}
          >
            {uiText.graphDeleteEdge}
          </button>
        </div>
      ) : null}

      {editMode && selectedBlock ? (
        <div className="absolute bottom-2 left-2 z-20 max-h-[42%] w-[min(520px,calc(100%-1rem))] overflow-auto">
          <div className="mb-1 flex justify-end">
            <button
              type="button"
              title={editorHidden ? uiText.graphEditorShow : uiText.graphEditorHide}
              aria-label={editorHidden ? uiText.graphEditorShow : uiText.graphEditorHide}
              className="rounded border border-slate-600 bg-slate-950/90 px-2 py-0.5 text-[10px] font-semibold text-slate-200 hover:bg-slate-800"
              onClick={() => setEditorHidden((value) => !value)}
            >
              {uiText.collapseToggle}
            </button>
          </div>
          {!editorHidden ? (
            <div className="rounded border border-slate-600 bg-slate-950/95 p-2 shadow-lg">
              <div className="mb-1 flex flex-wrap items-center gap-2">
                <label className="text-[10px] uppercase tracking-wide text-slate-500">
                  {uiText.graphLabelEdit}
                </label>
                {canReorder ? (
                  <>
                    <button
                      type="button"
                      className="rounded border border-slate-700 px-2 py-0.5 text-[10px] text-slate-200 hover:bg-slate-800"
                      onClick={() => reorder("up")}
                    >
                      {uiText.graphMoveUp}
                    </button>
                    <button
                      type="button"
                      className="rounded border border-slate-700 px-2 py-0.5 text-[10px] text-slate-200 hover:bg-slate-800"
                      onClick={() => reorder("down")}
                    >
                      {uiText.graphMoveDown}
                    </button>
                  </>
                ) : null}
                {canDeleteSelected ? (
                  <button
                    type="button"
                    className="rounded border border-red-800 px-2 py-0.5 text-[10px] text-red-200 hover:bg-red-950/50"
                    onClick={removeSelectedBlock}
                  >
                    {uiText.graphDeleteBlock}
                  </button>
                ) : null}
              </div>
              {selectedBlock.editable !== false ? (
                <div className="space-y-2">
                  <input
                    key={`${selectedBlock.id}-label`}
                    className="w-full rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-100"
                    defaultValue={selectedBlock.label}
                    onBlur={(event) => {
                      const value = event.target.value.trim();
                      if (value && value !== selectedBlock.label) {
                        commitBlockFields(value, selectedBlock.source_snippet ?? "");
                      }
                    }}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        (event.target as HTMLInputElement).blur();
                      }
                    }}
                  />
                  <label className="block text-[10px] uppercase tracking-wide text-slate-500">
                    {uiText.graphSnippetEdit}
                  </label>
                  <textarea
                    key={`${selectedBlock.id}-snippet`}
                    className="min-h-[72px] w-full rounded border border-slate-700 bg-slate-900 px-2 py-1 font-mono text-[11px] text-slate-100"
                    defaultValue={selectedBlock.source_snippet ?? ""}
                    onBlur={(event) => {
                      const value = event.target.value;
                      if (value !== (selectedBlock.source_snippet ?? "")) {
                        commitBlockFields(selectedBlock.label, value);
                      }
                    }}
                  />
                </div>
              ) : (
                <div className="text-xs text-zinc-400">{selectedBlock.label}</div>
              )}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function PanelHeaderButton({
  label,
  title,
  onClick,
  disabled,
  accent,
}: {
  label: string;
  title?: string;
  onClick?: () => void;
  disabled?: boolean;
  accent?: "emerald" | "sky" | "zinc";
}) {
  const accentClass =
    accent === "emerald"
      ? "border-emerald-700 text-emerald-100 hover:bg-emerald-950/50"
      : accent === "sky"
        ? "border-sky-700 text-sky-100 hover:bg-sky-950/40"
        : "border-slate-600 text-slate-200 hover:bg-slate-800";
  return (
    <button
      type="button"
      disabled={disabled || !onClick}
      title={title ?? label}
      aria-label={title ?? label}
      className={`rounded border px-2 py-0.5 text-[10px] font-semibold leading-none disabled:opacity-40 ${accentClass}`}
      onClick={onClick}
    >
      {label}
    </button>
  );
}

export function GraphWorkspace(props: GraphWorkspaceProps) {
  const {
    collapsed = false,
    fullscreen = false,
    editMode = false,
    schemeDirty = false,
    saveBusy = false,
    compact = false,
  } = props;

  if (compact) {
    return (
      <div className="h-full min-h-[220px] bg-slate-900">
        <ReactFlowProvider>
          <GraphCanvas {...props} editMode={false} />
        </ReactFlowProvider>
      </div>
    );
  }

  const header = (
    <div className="flex shrink-0 items-center justify-between gap-2 border-b border-zinc-800 bg-slate-950/80 px-3 py-1.5">
      <div className="min-w-0 truncate text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
        {uiText.graphTitle}
        {schemeDirty ? (
          <span className="ml-2 normal-case tracking-normal text-amber-300">
            ({uiText.graphDirty})
          </span>
        ) : null}
      </div>
      <div className="flex shrink-0 flex-wrap justify-end gap-1">
        <PanelHeaderButton
          label={editMode ? uiText.graphEditOff : uiText.graphEditOn}
          onClick={() => {
            if (!props.scratch && props.onCreateBlankScheme) {
              props.onCreateBlankScheme();
              return;
            }
            props.onToggleEdit?.();
          }}
          accent={editMode ? "sky" : "zinc"}
        />
        {!props.scratch && props.onCreateBlankScheme ? (
          <PanelHeaderButton
            label={uiText.graphCreateBlank}
            onClick={props.onCreateBlankScheme}
            accent="sky"
          />
        ) : null}
        {editMode ? (
          <>
            <PanelHeaderButton
              label={uiText.graphUndo}
              onClick={props.onUndo}
              disabled={!props.canUndo}
              accent="zinc"
            />
            <PanelHeaderButton
              label={uiText.graphExitNoSave}
              onClick={props.onExitWithoutSave}
              accent="zinc"
            />
            <PanelHeaderButton
              label={saveBusy ? uiText.graphSaveBusy : uiText.graphSaveGenerate}
              onClick={props.onSaveScheme}
              disabled={saveBusy || !schemeDirty}
              accent="emerald"
            />
          </>
        ) : null}
        <PanelHeaderButton
          label={fullscreen ? uiText.graphExitFullscreen : uiText.graphFullscreen}
          onClick={props.onToggleFullscreen}
        />
        {!fullscreen ? (
          <PanelHeaderButton
            label={collapsed ? uiText.expandToggle : uiText.collapseToggle}
            title={collapsed ? uiText.graphExpand : uiText.graphCollapse}
            onClick={props.onToggleCollapsed}
          />
        ) : null}
      </div>
    </div>
  );

  if (collapsed && !fullscreen) {
    return (
      <section className="flex h-full min-h-0 flex-col bg-slate-900">{header}</section>
    );
  }

  return (
    <section
      className={`flex min-h-0 flex-col bg-slate-900 ${
        fullscreen ? "fixed inset-0 z-50 border-0 shadow-2xl" : "h-full"
      }`}
    >
      {header}
      <div className="min-h-0 flex-1">
        <ReactFlowProvider>
          <GraphCanvas {...props} />
        </ReactFlowProvider>
      </div>
    </section>
  );
}
