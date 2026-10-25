"use client";

import { Handle, NodeResizer, Position, type NodeProps } from "@xyflow/react";
import {
  AlertTriangle,
  Box,
  Cog,
  Plus,
  Square,
  TriangleAlert,
  X,
} from "lucide-react";
import type { CSSProperties, ReactNode } from "react";

import { uiText } from "@/shared/i18n/ru";
import {
  accentForKind,
  schemeColors,
  type SchemeMarker,
} from "@/shared/lib/schemeTheme";

export type ScratchNodeData = {
  label: string;
  kind: string;
  color: string;
  startLine: number | null;
  startColumn: number | null;
  editable?: boolean;
  connectable?: boolean;
  snippet?: string;
  title?: string;
  isContainer?: boolean;
  marker?: SchemeMarker | null;
  icon?: "method" | "variable" | "operation" | "callout" | "return" | "continue";
};

const handleStyle = (visible: boolean): CSSProperties => ({
  width: 9,
  height: 9,
  background: "#f8fafc",
  border: "2px solid #0f172a",
  opacity: visible ? 1 : 0.4,
});

/** Краткая подпись на блоке; полный код - в title / свойствах. */
function shortLabel(label: string, max = 42): string {
  const text = label.trim();
  if (text.length <= max) {
    return text;
  }
  return `${text.slice(0, max)}...`;
}

function blockHoverTitle(label: string, snippet?: string): string {
  const code = (snippet ?? "").trim();
  if (code.length > 0) {
    return code.length > 400 ? `${code.slice(0, 400)}...` : code;
  }
  return label.trim();
}

function FlowHandle({
  type,
  position,
  id,
  visible,
  title,
  style,
}: {
  type: "source" | "target";
  position: Position;
  id: string;
  visible: boolean;
  title: string;
  style?: CSSProperties;
}) {
  return (
    <Handle
      type={type}
      position={position}
      id={id}
      title={title}
      aria-label={title}
      style={{ ...handleStyle(visible), ...style }}
    />
  );
}

function connectable(data: ScratchNodeData): boolean {
  return data.connectable !== false;
}

function glowBorder(accent: string, glow: string, radius: number | string): CSSProperties {
  return {
    background: schemeColors.surface,
    color: schemeColors.text,
    border: `2px solid ${accent}`,
    borderRadius: radius,
    boxShadow: `0 0 0 1px ${accent}33, 0 0 18px ${glow}, 0 10px 28px rgba(0,0,0,0.35)`,
  };
}

function MarkerBadge({ marker }: { marker?: SchemeMarker | null }) {
  if (!marker || marker.count <= 0) {
    return null;
  }
  const isError = marker.severity === "error";
  const bg = isError ? "#ef4444" : "#eab308";
  return (
    <div
      title={isError ? uiText.graphMarkerError : uiText.graphMarkerWarning}
      style={{
        position: "absolute",
        top: -8,
        right: -8,
        zIndex: 5,
        minWidth: 20,
        height: 20,
        padding: "0 5px",
        borderRadius: 999,
        background: bg,
        color: "#0f172a",
        fontSize: 10,
        fontWeight: 800,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        boxShadow: `0 0 12px ${bg}`,
        border: "2px solid #0f172a",
      }}
    >
      {marker.count > 1 ? marker.count : isError ? "!" : "!"}
    </div>
  );
}

function NodeIcon({ kind }: { kind: ScratchNodeData["icon"] | string }) {
  const size = 14;
  const stroke = 2.2;
  if (kind === "method") {
    return <Cog size={size} strokeWidth={stroke} />;
  }
  if (kind === "variable") {
    return <Square size={size} strokeWidth={stroke} />;
  }
  if (kind === "callout") {
    return <AlertTriangle size={size} strokeWidth={stroke} />;
  }
  if (kind === "continue" || kind === "return") {
    return <X size={size} strokeWidth={stroke} />;
  }
  return <Plus size={size} strokeWidth={stroke} />;
}

function HeaderRow({
  title,
  accent,
  icon,
}: {
  title: string;
  accent: string;
  icon?: ScratchNodeData["icon"] | string;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        color: accent,
        fontSize: 10,
        fontWeight: 800,
        letterSpacing: "0.05em",
        textTransform: "uppercase",
        marginBottom: 4,
      }}
    >
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: 20,
          height: 20,
          borderRadius: 6,
          background: `${accent}22`,
          border: `1px solid ${accent}66`,
        }}
      >
        <NodeIcon kind={icon ?? "operation"} />
      </span>
      <span>{title}</span>
    </div>
  );
}

function BodyText({ label }: { label: string; snippet?: string }) {
  return (
    <div
      style={{
        fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
        fontSize: 11,
        color: schemeColors.text,
        wordBreak: "break-word",
        lineHeight: 1.35,
      }}
    >
      {shortLabel(label)}
    </div>
  );
}

function EditResizer({
  enabled,
  selected,
  minWidth = 120,
  minHeight = 56,
}: {
  enabled: boolean;
  selected?: boolean;
  minWidth?: number;
  minHeight?: number;
}) {
  if (!enabled) {
    return null;
  }
  return (
    <NodeResizer
      isVisible={Boolean(selected)}
      minWidth={minWidth}
      minHeight={minHeight}
      keepAspectRatio={false}
      lineStyle={{ borderColor: "#38bdf8", borderWidth: 1 }}
      handleStyle={{
        width: 8,
        height: 8,
        borderRadius: 2,
        background: "#38bdf8",
        border: "1px solid #0f172a",
      }}
    />
  );
}

function Shell({
  accent,
  glow,
  radius,
  children,
  marker,
  extra,
  resizable,
  selected,
}: {
  accent: string;
  glow: string;
  radius: number | string;
  children: ReactNode;
  marker?: SchemeMarker | null;
  extra?: CSSProperties;
  resizable?: boolean;
  selected?: boolean;
}) {
  return (
    <div style={{ position: "relative", width: "100%", height: "100%", boxSizing: "border-box" }}>
      <EditResizer enabled={Boolean(resizable)} selected={selected} />
      <MarkerBadge marker={marker} />
      <div
        style={{
          ...glowBorder(accent, glow, radius),
          width: "100%",
          height: "100%",
          minWidth: 0,
          minHeight: 0,
          padding: "10px 12px",
          fontSize: 11,
          boxSizing: "border-box",
          overflow: "hidden",
          ...extra,
        }}
      >
        {children}
      </div>
    </div>
  );
}

/** Начало / конец. */
export function TerminalNode({ data, selected }: NodeProps) {
  const node = data as ScratchNodeData;
  const show = connectable(node);
  const { accent, glow } = accentForKind(node.kind);
  const hover = blockHoverTitle(node.label, node.snippet);
  return (
    <Shell
      accent={accent}
      glow={glow}
      radius={999}
      marker={node.marker}
      resizable={show}
      selected={selected}
      extra={{ textAlign: "center" }}
    >
      {node.kind !== "start" ? (
        <FlowHandle
          type="target"
          position={Position.Top}
          id="in"
          visible={show}
          title={uiText.handleIn}
        />
      ) : null}
      <div title={hover}>
        <HeaderRow title={node.title ?? node.kind} accent={accent} icon="return" />
        <div style={{ fontWeight: 700 }}>{shortLabel(node.label, 28)}</div>
      </div>
      {node.kind !== "end" ? (
        <FlowHandle
          type="source"
          position={Position.Bottom}
          id="out"
          visible={show}
          title={uiText.handleOut}
        />
      ) : null}
    </Shell>
  );
}

/** Метод / класс: сильное скругление, фиолетовое свечение, иконка шестерёнки. */
export function ModuleHatNode({ data, selected }: NodeProps) {
  const node = data as ScratchNodeData;
  const show = connectable(node);
  const { accent, glow } = accentForKind(node.kind);
  const hover = blockHoverTitle(node.label, node.snippet);
  return (
    <Shell accent={accent} glow={glow} radius={22} marker={node.marker} resizable={show} selected={selected}>
      <FlowHandle
        type="target"
        position={Position.Top}
        id="in"
        visible={show}
        title={uiText.handleIn}
      />
      <div title={hover}>
        <HeaderRow title={node.title ?? "Метод"} accent={accent} icon="method" />
        <BodyText label={node.label} />
      </div>
      <FlowHandle
        type="source"
        position={Position.Bottom}
        id="out"
        visible={show}
        title={uiText.handleOut}
      />
      <FlowHandle
        type="source"
        position={Position.Right}
        id="body"
        visible={show}
        title={uiText.handleBody}
        style={{ top: "70%" }}
      />
      <FlowHandle
        type="source"
        position={Position.Right}
        id="callout"
        visible={show}
        title={uiText.handleCallout}
        style={{ top: "40%" }}
      />
    </Shell>
  );
}

/** Переменная / операция. */
export function ProcessNode({ data, selected }: NodeProps) {
  const node = data as ScratchNodeData;
  const show = connectable(node);
  const { accent, glow } = accentForKind(node.kind);
  const icon =
    node.kind === "variable" || node.kind === "parameter" ? "variable" : "operation";
  const hover = blockHoverTitle(node.label, node.snippet);
  return (
    <Shell accent={accent} glow={glow} radius={12} marker={node.marker} resizable={show} selected={selected}>
      <FlowHandle
        type="target"
        position={Position.Top}
        id="in"
        visible={show}
        title={uiText.handleIn}
      />
      <FlowHandle
        type="source"
        position={Position.Right}
        id="callout"
        visible={show}
        title={uiText.handleCallout}
        style={{ top: "50%" }}
      />
      <div title={hover}>
        <HeaderRow title={node.title ?? "Операция"} accent={accent} icon={icon} />
        <BodyText label={node.label} />
      </div>
      <FlowHandle
        type="source"
        position={Position.Bottom}
        id="out"
        visible={show}
        title={uiText.handleOut}
      />
    </Shell>
  );
}

/**
 * Условие: ромб (квадрат 45°), размер от узла React Flow (адаптивный + ручной resize).
 */
export function DecisionNode({ data, selected }: NodeProps) {
  const node = data as ScratchNodeData;
  const show = connectable(node);
  const { accent, glow } = accentForKind("if");
  const hover = blockHoverTitle(node.label, node.snippet);
  return (
    <div
      title={hover}
      style={{
        width: "100%",
        height: "100%",
        minWidth: 140,
        minHeight: 110,
        position: "relative",
        boxSizing: "border-box",
      }}
    >
      <EditResizer enabled={show} selected={selected} minWidth={140} minHeight={110} />
      <MarkerBadge marker={node.marker} />
      <FlowHandle
        type="target"
        position={Position.Top}
        id="in"
        visible={show}
        title={uiText.handleIn}
        style={{ top: 2 }}
      />
      <div
        style={{
          position: "absolute",
          left: "50%",
          top: "50%",
          width: "62%",
          aspectRatio: "1 / 1",
          transform: "translate(-50%, -50%) rotate(45deg)",
          background: "#422006",
          border: `2.5px solid ${accent}`,
          borderRadius: 12,
          boxShadow: `0 0 0 1px ${accent}44, 0 0 22px ${glow}`,
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: "22% 16%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          textAlign: "center",
          zIndex: 1,
          pointerEvents: "none",
        }}
      >
        <div
          style={{
            color: accent,
            fontSize: 10,
            fontWeight: 800,
            letterSpacing: "0.05em",
            textTransform: "uppercase",
            marginBottom: 4,
          }}
        >
          {node.title ?? "Условие"}
        </div>
        <BodyText label={node.label} />
      </div>
      <FlowHandle
        type="source"
        position={Position.Bottom}
        id="body"
        visible={show}
        title={uiText.handleBody}
      />
      <FlowHandle
        type="source"
        position={Position.Bottom}
        id="out"
        visible={show}
        title={uiText.handleOut}
        style={{ left: "78%" }}
      />
      <FlowHandle
        type="source"
        position={Position.Right}
        id="else"
        visible={show}
        title={uiText.handleElse}
      />
      <FlowHandle
        type="source"
        position={Position.Right}
        id="callout"
        visible={show}
        title={uiText.handleCallout}
        style={{ top: "28%" }}
      />
    </div>
  );
}

/** Компактный заголовок цикла (fallback без контейнера). */
export function LoopNode({ data, selected }: NodeProps) {
  const node = data as ScratchNodeData;
  const show = connectable(node);
  const { accent, glow } = accentForKind(node.kind);
  const hover = blockHoverTitle(node.label, node.snippet);
  return (
    <Shell accent={accent} glow={glow} radius={14} marker={node.marker} resizable={show} selected={selected}>
      <FlowHandle
        type="target"
        position={Position.Top}
        id="in"
        visible={show}
        title={uiText.handleIn}
      />
      <div title={hover}>
        <HeaderRow title={node.title ?? "Цикл"} accent={accent} icon="method" />
        <BodyText label={node.label} />
      </div>
      <FlowHandle
        type="source"
        position={Position.Bottom}
        id="body"
        visible={show}
        title={uiText.handleBody}
      />
      <FlowHandle
        type="source"
        position={Position.Right}
        id="out"
        visible={show}
        title={uiText.handleOut}
        style={{ top: "50%" }}
      />
    </Shell>
  );
}

/**
 * Структурный контейнер (цикл / try / switch / else / ...):
 * шапка с условием + тело. body - вниз во внутреннюю зону, out - наружу снизу.
 */
export function StructureContainerNode({ data, selected }: NodeProps) {
  const node = data as ScratchNodeData;
  const show = connectable(node);
  const { accent, glow } = accentForKind(node.kind);
  const hover = blockHoverTitle(node.label, node.snippet);
  const headerTint =
    node.kind === "try" || node.kind === "catch" || node.kind === "finally"
      ? "rgba(49, 46, 129, 0.85)"
      : node.kind === "switch" || node.kind === "case"
        ? "rgba(120, 53, 15, 0.85)"
        : "rgba(15, 23, 42, 0.85)";
  const bodyTint =
    node.kind === "try" || node.kind === "catch" || node.kind === "finally"
      ? "rgba(67, 56, 202, 0.14)"
      : node.kind === "switch" || node.kind === "case"
        ? "rgba(180, 83, 9, 0.12)"
        : "rgba(88, 28, 135, 0.16)";
  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        borderRadius: 18,
        border: `3px solid ${accent}`,
        background: bodyTint,
        boxShadow: `inset 0 0 0 2px ${accent}28, 0 0 22px ${glow}`,
        position: "relative",
        overflow: "visible",
        boxSizing: "border-box",
      }}
    >
      <EditResizer enabled={show} selected={selected} minWidth={220} minHeight={180} />
      <MarkerBadge marker={node.marker} />
      <FlowHandle
        type="target"
        position={Position.Top}
        id="in"
        visible={show}
        title={uiText.handleIn}
      />
      <div
        title={hover}
        style={{
          padding: "10px 14px",
          borderBottom: `1px solid ${accent}66`,
          background: headerTint,
          borderRadius: "15px 15px 0 0",
          minHeight: 54,
        }}
      >
        <HeaderRow title={node.title ?? "Контейнер"} accent={accent} icon="method" />
        <div
          style={{
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
            fontSize: 11,
            color: "#f8fafc",
            wordBreak: "break-word",
          }}
        >
          {shortLabel(node.label, 48)}
        </div>
      </div>
      <div
        style={{
          position: "absolute",
          left: 10,
          right: 10,
          top: 66,
          bottom: 26,
          borderRadius: 12,
          border: `2px dashed ${accent}77`,
          background: "rgba(15, 23, 42, 0.25)",
          pointerEvents: "none",
          color: `${accent}aa`,
          fontSize: 10,
          fontWeight: 700,
          padding: 8,
          letterSpacing: "0.04em",
          textTransform: "uppercase",
        }}
      >
        внутренний поток
      </div>
      {/* Body направлен вниз внутрь контейнера - стрелка не уходит наружу и не возвращается. */}
      <FlowHandle
        type="source"
        position={Position.Bottom}
        id="body"
        visible={show}
        title={uiText.handleBody}
        style={{
          top: 68,
          left: "50%",
          transform: "translate(-50%, -50%)",
        }}
      />
      <FlowHandle
        type="source"
        position={Position.Bottom}
        id="out"
        visible={show}
        title={uiText.handleOut}
      />
      <FlowHandle
        type="source"
        position={Position.Right}
        id="else"
        visible={show}
        title={uiText.handleElse}
        style={{ top: "28%" }}
      />
      <FlowHandle
        type="source"
        position={Position.Right}
        id="callout"
        visible={show}
        title={uiText.handleCallout}
        style={{ top: "55%" }}
      />
    </div>
  );
}

/** @deprecated alias для старых схем */
export const LoopContainerNode = StructureContainerNode;

/** return / break / continue. */
export function CapNode({ data, selected }: NodeProps) {
  const node = data as ScratchNodeData;
  const show = connectable(node);
  const { accent, glow } = accentForKind(node.kind);
  const icon = node.kind === "return" ? "return" : "continue";
  const hover = blockHoverTitle(node.label, node.snippet);
  return (
    <Shell accent={accent} glow={glow} radius={18} marker={node.marker} resizable={show} selected={selected}>
      <FlowHandle
        type="target"
        position={Position.Top}
        id="in"
        visible={show}
        title={uiText.handleIn}
      />
      <FlowHandle
        type="target"
        position={Position.Left}
        id="in-side"
        visible={show}
        title={uiText.handleIn}
      />
      <FlowHandle
        type="source"
        position={Position.Right}
        id="callout"
        visible={show}
        title={uiText.handleCallout}
        style={{ top: "45%" }}
      />
      <div title={hover}>
        <HeaderRow title={node.title ?? "Выход"} accent={accent} icon={icon} />
        <BodyText label={node.label} />
      </div>
      <FlowHandle
        type="source"
        position={Position.Bottom}
        id="out"
        visible={show}
        title={uiText.handleOut}
      />
    </Shell>
  );
}

/** Внешний вызов: золотистый блок за пределами контейнера. */
export function ExternalCallNode({ data, selected }: NodeProps) {
  const node = data as ScratchNodeData;
  const show = connectable(node);
  const { accent, glow } = accentForKind("call");
  const hover = blockHoverTitle(node.label, node.snippet);
  return (
    <Shell
      accent={accent}
      glow={glow}
      radius={10}
      marker={node.marker}
      resizable={show}
      selected={selected}
      extra={{
        background: "#422006",
        borderStyle: "solid",
      }}
    >
      <FlowHandle
        type="target"
        position={Position.Left}
        id="in"
        visible={show}
        title={uiText.handleIn}
      />
      <div title={hover}>
        <HeaderRow title={node.title ?? "Внешний вызов"} accent={accent} icon="callout" />
        <BodyText label={node.label} />
      </div>
      <div
        style={{
          marginTop: 6,
          display: "flex",
          alignItems: "center",
          gap: 4,
          color: accent,
          fontSize: 9,
          fontWeight: 700,
        }}
      >
        <TriangleAlert size={12} />
        <span>{uiText.graphExternalCallHint}</span>
      </div>
    </Shell>
  );
}

/** Якорь пунктира к панели анализа справа. */
export function AnalysisAnchorNode({ data }: NodeProps) {
  const node = data as ScratchNodeData;
  const severity = node.marker?.severity ?? "error";
  const color = severity === "warning" ? schemeColors.decision : schemeColors.analysis;
  return (
    <div
      title={uiText.graphAnalysisLink}
      style={{
        width: 28,
        height: 28,
        borderRadius: 999,
        border: `2px dashed ${color}`,
        background: `${color}22`,
        boxShadow: `0 0 14px ${color}66`,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        color,
      }}
    >
      <Box size={12} />
      <Handle type="target" position={Position.Left} id="in" style={{ opacity: 0 }} />
    </div>
  );
}

export const scratchNodeTypes = {
  modularTerminal: TerminalNode,
  modularModule: ModuleHatNode,
  modularProcess: ProcessNode,
  modularDecision: DecisionNode,
  modularLoop: LoopNode,
  modularCap: CapNode,
  structureContainer: StructureContainerNode,
  // Совместимость со старыми сохранёнными схемами.
  loopContainer: StructureContainerNode,
  modularCallout: ExternalCallNode,
  modularAnalysis: AnalysisAnchorNode,
};

export function scratchFlowNodeType(kind: string): keyof typeof scratchNodeTypes {
  if (kind === "start" || kind === "end") {
    return "modularTerminal";
  }
  if (
    kind === "method" ||
    kind === "class" ||
    kind === "module" ||
    kind === "interface" ||
    kind === "enum" ||
    kind === "record"
  ) {
    return "modularModule";
  }
  if (kind === "if") {
    return "modularDecision";
  }
  if (
    kind === "while" ||
    kind === "do" ||
    kind === "for" ||
    kind === "foreach" ||
    kind === "try" ||
    kind === "catch" ||
    kind === "finally" ||
    kind === "switch" ||
    kind === "else" ||
    kind === "case" ||
    kind === "synchronized" ||
    kind === "labeled"
  ) {
    return "structureContainer";
  }
  if (kind === "block") {
    return "modularLoop";
  }
  if (
    kind === "return" ||
    kind === "break" ||
    kind === "continue" ||
    kind === "throw" ||
    kind === "yield"
  ) {
    return "modularCap";
  }
  return "modularProcess";
}
