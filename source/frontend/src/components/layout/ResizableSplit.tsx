"use client";

import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react";

type SplitOrientation = "horizontal" | "vertical";

interface ResizableSplitProps {
  orientation: SplitOrientation;
  /** Доля первой панели 0..1. */
  initialRatio?: number;
  minRatio?: number;
  maxRatio?: number;
  storageKey?: string;
  first: ReactNode;
  second: ReactNode;
  firstCollapsed?: boolean;
  secondCollapsed?: boolean;
  className?: string;
  /** Высота/ширина свёрнутой панели (px). */
  collapsedSizePx?: number;
}

function readStoredRatio(key: string | undefined, fallback: number): number {
  if (!key || typeof window === "undefined") {
    return fallback;
  }
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) {
      return fallback;
    }
    const value = Number(raw);
    return Number.isFinite(value) ? value : fallback;
  } catch {
    return fallback;
  }
}

export function ResizableSplit({
  orientation,
  initialRatio = 0.55,
  minRatio = 0.15,
  maxRatio = 0.85,
  storageKey,
  first,
  second,
  firstCollapsed = false,
  secondCollapsed = false,
  className = "",
  collapsedSizePx = 36,
}: ResizableSplitProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [ratio, setRatio] = useState(() =>
    clamp(readStoredRatio(storageKey, initialRatio), minRatio, maxRatio),
  );
  const [dragging, setDragging] = useState(false);
  const handleId = useId();

  useEffect(() => {
    if (!storageKey || typeof window === "undefined") {
      return;
    }
    try {
      window.localStorage.setItem(storageKey, String(ratio));
    } catch {
      // ignore quota / private mode
    }
  }, [ratio, storageKey]);

  const onPointerDown = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      if (firstCollapsed || secondCollapsed) {
        return;
      }
      event.preventDefault();
      const target = event.currentTarget;
      target.setPointerCapture(event.pointerId);
      setDragging(true);

      const onMove = (moveEvent: PointerEvent) => {
        const box = containerRef.current?.getBoundingClientRect();
        if (!box) {
          return;
        }
        const next =
          orientation === "horizontal"
            ? (moveEvent.clientY - box.top) / box.height
            : (moveEvent.clientX - box.left) / box.width;
        setRatio(clamp(next, minRatio, maxRatio));
      };

      const onUp = (upEvent: PointerEvent) => {
        target.releasePointerCapture(upEvent.pointerId);
        setDragging(false);
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
      };

      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
    },
    [firstCollapsed, secondCollapsed, maxRatio, minRatio, orientation],
  );

  const isHorizontal = orientation === "horizontal";
  const bothOpen = !firstCollapsed && !secondCollapsed;

  let firstStyle: CSSProperties;
  let secondStyle: CSSProperties;
  if (firstCollapsed && secondCollapsed) {
    firstStyle = { flex: "0 0 auto", height: collapsedSizePx };
    secondStyle = { flex: "0 0 auto", height: collapsedSizePx };
  } else if (firstCollapsed) {
    firstStyle = isHorizontal
      ? { flex: `0 0 ${collapsedSizePx}px`, minHeight: collapsedSizePx }
      : { flex: `0 0 ${collapsedSizePx}px`, minWidth: collapsedSizePx };
    secondStyle = { flex: "1 1 0%", minHeight: 0, minWidth: 0 };
  } else if (secondCollapsed) {
    firstStyle = { flex: "1 1 0%", minHeight: 0, minWidth: 0 };
    secondStyle = isHorizontal
      ? { flex: `0 0 ${collapsedSizePx}px`, minHeight: collapsedSizePx }
      : { flex: `0 0 ${collapsedSizePx}px`, minWidth: collapsedSizePx };
  } else {
    const firstPct = `${ratio * 100}%`;
    const secondPct = `${(1 - ratio) * 100}%`;
    firstStyle = isHorizontal
      ? { flex: `1 1 ${firstPct}`, minHeight: 80, height: firstPct }
      : { flex: `1 1 ${firstPct}`, minWidth: 120, width: firstPct };
    secondStyle = isHorizontal
      ? { flex: `1 1 ${secondPct}`, minHeight: 80, height: secondPct }
      : { flex: `1 1 ${secondPct}`, minWidth: 120, width: secondPct };
  }

  return (
    <div
      ref={containerRef}
      className={`flex min-h-0 min-w-0 ${isHorizontal ? "flex-col" : "flex-row"} ${className}`}
    >
      <div className="flex min-h-0 min-w-0 flex-col overflow-hidden" style={firstStyle}>
        {first}
      </div>

      {bothOpen ? (
        <div
          id={handleId}
          role="separator"
          aria-orientation={isHorizontal ? "horizontal" : "vertical"}
          aria-valuenow={Math.round(ratio * 100)}
          aria-label="Изменить размер панелей"
          title="Потяните мышью, чтобы изменить размер"
          tabIndex={0}
          onPointerDown={onPointerDown}
          onKeyDown={(event) => {
            const step = event.shiftKey ? 0.08 : 0.03;
            if (isHorizontal) {
              if (event.key === "ArrowUp") {
                event.preventDefault();
                setRatio((value) => clamp(value - step, minRatio, maxRatio));
              } else if (event.key === "ArrowDown") {
                event.preventDefault();
                setRatio((value) => clamp(value + step, minRatio, maxRatio));
              }
            } else if (event.key === "ArrowLeft") {
              event.preventDefault();
              setRatio((value) => clamp(value - step, minRatio, maxRatio));
            } else if (event.key === "ArrowRight") {
              event.preventDefault();
              setRatio((value) => clamp(value + step, minRatio, maxRatio));
            }
          }}
          className={
            isHorizontal
              ? `group relative z-10 h-2 shrink-0 cursor-row-resize bg-zinc-900 hover:bg-sky-800/60 ${
                  dragging ? "bg-sky-700/70" : ""
                }`
              : `group relative z-10 w-2 shrink-0 cursor-col-resize bg-zinc-900 hover:bg-sky-800/60 ${
                  dragging ? "bg-sky-700/70" : ""
                }`
          }
        >
          <div
            className={
              isHorizontal
                ? "absolute inset-x-1/3 top-1/2 h-0.5 -translate-y-1/2 rounded bg-zinc-600 group-hover:bg-sky-400"
                : "absolute inset-y-1/3 left-1/2 w-0.5 -translate-x-1/2 rounded bg-zinc-600 group-hover:bg-sky-400"
            }
          />
        </div>
      ) : null}

      <div className="flex min-h-0 min-w-0 flex-col overflow-hidden" style={secondStyle}>
        {second}
      </div>
    </div>
  );
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}
