/** История правок логической схемы для Undo (Ctrl+Z). */

import { schemeStructureKey } from "@/shared/lib/schemeEdit";
import type { ScratchProgram } from "@/shared/types/workspace";

const DEFAULT_LIMIT = 40;

export interface SchemeHistoryState {
  entries: ScratchProgram[];
  index: number;
}

export function createSchemeHistory(initial: ScratchProgram | null): SchemeHistoryState {
  if (!initial) {
    return { entries: [], index: -1 };
  }
  return { entries: [initial], index: 0 };
}

export function pushSchemeHistory(
  state: SchemeHistoryState,
  next: ScratchProgram,
  limit: number = DEFAULT_LIMIT,
): SchemeHistoryState {
  const current = state.entries[state.index];
  if (current && schemeStructureKey(current) === schemeStructureKey(next)) {
    return state;
  }
  const trimmed = state.entries.slice(0, state.index + 1);
  trimmed.push(next);
  while (trimmed.length > limit) {
    trimmed.shift();
  }
  return {
    entries: trimmed,
    index: trimmed.length - 1,
  };
}

export function undoSchemeHistory(
  state: SchemeHistoryState,
): { state: SchemeHistoryState; program: ScratchProgram | null } {
  if (state.index <= 0) {
    return { state, program: state.entries[state.index] ?? null };
  }
  const index = state.index - 1;
  return {
    state: { ...state, index },
    program: state.entries[index] ?? null,
  };
}

export function canUndoScheme(state: SchemeHistoryState): boolean {
  return state.index > 0;
}

export function resetSchemeHistory(program: ScratchProgram | null): SchemeHistoryState {
  return createSchemeHistory(program);
}
