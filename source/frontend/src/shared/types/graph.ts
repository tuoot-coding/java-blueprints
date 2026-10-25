/**
 * Заготовка типов для будущих узлов CFG.
 * Финальный контракт будет синхронизирован с Backend OpenAPI.
 * Не используйте эти типы для генерации фиктивного графа.
 */

export type FutureGraphNodeKind =
  | "entry"
  | "exit"
  | "statement"
  | "branch"
  | "loop"
  | "unsupported";

export interface FutureGraphNode {
  id: string;
  kind: FutureGraphNodeKind;
  label: string;
  sourceStartByte?: number;
  sourceEndByte?: number;
}

export interface FutureGraphEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
}
