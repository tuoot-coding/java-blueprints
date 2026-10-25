/** Семантические цвета и подписи узлов логической схемы. */

export type SchemeSeverity = "error" | "warning" | "info";

export interface SchemeMarker {
  severity: SchemeSeverity;
  count: number;
}

export const schemeColors = {
  method: "#a855f7",
  methodGlow: "rgba(168, 85, 247, 0.55)",
  return: "#22c55e",
  returnGlow: "rgba(34, 197, 94, 0.5)",
  variable: "#38bdf8",
  variableGlow: "rgba(56, 189, 248, 0.5)",
  operation: "#3b82f6",
  operationGlow: "rgba(59, 130, 246, 0.45)",
  interrupt: "#ef4444",
  interruptGlow: "rgba(239, 68, 68, 0.5)",
  decision: "#f59e0b",
  decisionGlow: "rgba(245, 158, 11, 0.55)",
  loop: "#c084fc",
  loopGlow: "rgba(192, 132, 252, 0.45)",
  tryBlock: "#818cf8",
  tryGlow: "rgba(129, 140, 248, 0.45)",
  switchBlock: "#f59e0b",
  switchGlow: "rgba(245, 158, 11, 0.4)",
  callout: "#eab308",
  calloutGlow: "rgba(234, 179, 8, 0.55)",
  analysis: "#f87171",
  edgeMain: "#cbd5e1",
  edgeBranch: "#fbbf24",
  /** Внутренний поток тела цикла/контейнера (отдельно от внешней цепочки). */
  edgeInner: "#c084fc",
  edgeCallout: "#eab308",
  edgeAnalysis: "#f87171",
  surface: "#0f172a",
  text: "#f1f5f9",
  muted: "#94a3b8",
} as const;

export function roleTitle(kind: string): string {
  const map: Record<string, string> = {
    class: "Класс",
    method: "Метод",
    start: "Начало",
    end: "Конец",
    if: "Условие",
    else: "Иначе",
    switch: "Выбор (switch)",
    case: "Ветка (case)",
    while: "Цикл (while)",
    do: "Цикл (do)",
    for: "Цикл (for)",
    foreach: "Цикл (for each)",
    try: "Попытка (try)",
    catch: "Перехват (catch)",
    finally: "Наконец (finally)",
    synchronized: "Синхронно",
    labeled: "Метка",
    assert: "Assert",
    yield: "Yield",
    interface: "Интерфейс",
    enum: "Enum",
    record: "Record",
    variable: "Переменная",
    parameter: "Параметр",
    assignment: "Операция",
    expression: "Операция",
    call: "Внешний вызов",
    return: "Возврат",
    break: "Прервать",
    continue: "Продолжить",
    throw: "Исключение",
    block: "Блок",
    unsupported: "Не поддержано",
  };
  return map[kind] ?? kind;
}

export function containerTitle(kind: string): string {
  if (kind === "foreach") {
    return "Цикл (for each)";
  }
  if (kind === "for") {
    return "Цикл (for)";
  }
  if (kind === "while") {
    return "Цикл (while)";
  }
  if (kind === "do") {
    return "Цикл (do)";
  }
  return roleTitle(kind);
}

/** Структурные элементы с телом-контейнером (шапка + вложенный подграф). */
export function isStructureContainerKind(kind: string): boolean {
  return (
    kind === "while" ||
    kind === "do" ||
    kind === "for" ||
    kind === "foreach" ||
    kind === "try" ||
    kind === "catch" ||
    kind === "finally" ||
    kind === "switch" ||
    kind === "synchronized" ||
    kind === "labeled" ||
    kind === "else" ||
    kind === "case"
  );
}

export function isLoopKind(kind: string): boolean {
  return kind === "while" || kind === "do" || kind === "for" || kind === "foreach";
}

export function isExitKind(kind: string): boolean {
  return kind === "return" || kind === "continue" || kind === "break" || kind === "throw";
}

export function accentForKind(kind: string): { accent: string; glow: string } {
  if (
    kind === "method" ||
    kind === "class" ||
    kind === "module" ||
    kind === "interface" ||
    kind === "enum" ||
    kind === "record"
  ) {
    return { accent: schemeColors.method, glow: schemeColors.methodGlow };
  }
  if (kind === "return" || kind === "start" || kind === "end") {
    return { accent: schemeColors.return, glow: schemeColors.returnGlow };
  }
  if (kind === "continue" || kind === "break" || kind === "throw") {
    return { accent: schemeColors.interrupt, glow: schemeColors.interruptGlow };
  }
  if (kind === "if") {
    return { accent: schemeColors.decision, glow: schemeColors.decisionGlow };
  }
  if (kind === "switch" || kind === "case") {
    return { accent: schemeColors.switchBlock, glow: schemeColors.switchGlow };
  }
  if (kind === "try" || kind === "catch" || kind === "finally" || kind === "synchronized") {
    return { accent: schemeColors.tryBlock, glow: schemeColors.tryGlow };
  }
  if (isLoopKind(kind) || kind === "else" || kind === "labeled") {
    return { accent: schemeColors.loop, glow: schemeColors.loopGlow };
  }
  if (kind === "call") {
    return { accent: schemeColors.callout, glow: schemeColors.calloutGlow };
  }
  if (kind === "variable" || kind === "parameter") {
    return { accent: schemeColors.variable, glow: schemeColors.variableGlow };
  }
  return { accent: schemeColors.operation, glow: schemeColors.operationGlow };
}
