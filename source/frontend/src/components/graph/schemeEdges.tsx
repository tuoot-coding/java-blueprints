"use client";

import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  getSmoothStepPath,
  type EdgeProps,
} from "@xyflow/react";

import { schemeColors } from "@/shared/lib/schemeTheme";

function OvalBadge({
  text,
  tone,
  selected,
}: {
  text: string;
  tone: "yes" | "no" | "neutral";
  selected?: boolean;
}) {
  const border =
    tone === "yes"
      ? "#4ade80"
      : tone === "no"
        ? "#f87171"
        : selected
          ? "#38bdf8"
          : "#64748b";
  const bg =
    tone === "yes"
      ? "rgba(15, 23, 42, 0.92)"
      : tone === "no"
        ? "rgba(15, 23, 42, 0.92)"
        : "rgba(15, 23, 42, 0.92)";
  const color =
    tone === "yes" ? "#86efac" : tone === "no" ? "#fca5a5" : "#e2e8f0";
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 9px",
        borderRadius: 999,
        border: `1px solid ${border}`,
        background: bg,
        color,
        fontSize: 10,
        fontWeight: 700,
        letterSpacing: "0.03em",
        boxShadow: selected
          ? "0 0 0 1px rgba(56,189,248,0.45), 0 4px 14px rgba(0,0,0,0.45)"
          : "0 4px 12px rgba(0,0,0,0.4)",
        whiteSpace: "nowrap",
        backdropFilter: "blur(4px)",
      }}
    >
      {text}
    </span>
  );
}

function badgeTone(label: string | undefined): "yes" | "no" | "neutral" {
  const value = (label ?? "").trim().toLowerCase();
  if (value === "да" || value === "yes" || value === "true" || value === "body") {
    return "yes";
  }
  if (value === "нет" || value === "no" || value === "false" || value === "else") {
    return "no";
  }
  return "neutral";
}

/** Основное ребро сверху вниз или ветка с овальным бейджем Да/Нет. */
export function SchemeFlowEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  label,
  style,
  markerEnd,
  data,
  selected,
}: EdgeProps) {
  const meta = data as { sideways?: boolean; flowScope?: string; linkKind?: string } | undefined;
  const sideways = Boolean(meta?.sideways);
  const innerDown = meta?.flowScope === "inner" && !sideways;
  // Внутренний поток (тело цикла) - короткий smooth-step вниз, без петли наружу.
  const [path, labelX, labelY] = sideways
    ? getSmoothStepPath({
        sourceX,
        sourceY,
        targetX,
        targetY,
        sourcePosition,
        targetPosition,
        borderRadius: 16,
      })
    : innerDown
      ? getSmoothStepPath({
          sourceX,
          sourceY,
          targetX,
          targetY,
          sourcePosition,
          targetPosition,
          borderRadius: 8,
          offset: 12,
        })
      : getBezierPath({
          sourceX,
          sourceY,
          targetX,
          targetY,
          sourcePosition,
          targetPosition,
        });
  const text = typeof label === "string" && label.trim().length > 0 ? label.trim() : undefined;
  const stroke = selected
    ? "#38bdf8"
    : (style?.stroke as string | undefined) ?? schemeColors.edgeMain;

  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        markerEnd={markerEnd}
        style={{
          ...style,
          stroke,
          strokeWidth: selected ? 3 : (style?.strokeWidth as number | undefined) ?? 2.2,
        }}
      />
      {text ? (
        <EdgeLabelRenderer>
          <div
            className="nopan"
            style={{
              position: "absolute",
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
              pointerEvents: "all",
              cursor: "pointer",
            }}
          >
            <OvalBadge text={text} tone={badgeTone(text)} selected={selected} />
          </div>
        </EdgeLabelRenderer>
      ) : null}
    </>
  );
}

/** Пунктир к внешнему вызову. */
export function SchemeCalloutEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style,
  markerEnd,
}: EdgeProps) {
  const [path] = getSmoothStepPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    borderRadius: 12,
  });
  return (
    <BaseEdge
      id={id}
      path={path}
      markerEnd={markerEnd}
      style={{
        stroke: schemeColors.edgeCallout,
        strokeWidth: 1.8,
        strokeDasharray: "6 5",
        ...style,
      }}
    />
  );
}

/** Пунктир от узла с ошибкой к якорю анализа справа. */
export function SchemeAnalysisEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style,
  markerEnd,
  data,
}: EdgeProps) {
  const severity = (data as { severity?: string } | undefined)?.severity ?? "error";
  const stroke = severity === "warning" ? schemeColors.decision : schemeColors.edgeAnalysis;
  const [path] = getSmoothStepPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    borderRadius: 8,
  });
  return (
    <BaseEdge
      id={id}
      path={path}
      markerEnd={markerEnd}
      style={{
        stroke,
        strokeWidth: 1.6,
        strokeDasharray: "4 4",
        opacity: 0.85,
        ...style,
      }}
    />
  );
}

export const schemeEdgeTypes = {
  schemeFlow: SchemeFlowEdge,
  schemeCallout: SchemeCalloutEdge,
  schemeAnalysis: SchemeAnalysisEdge,
};
