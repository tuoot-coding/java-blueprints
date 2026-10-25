/** Локальный документ редактора (без серверной ревизии). */

export interface LocalJavaDocument {
  fileName: string | null;
  sourceText: string;
  /** Исходный текст после последнего открытия файла или явного сброса dirty. */
  baselineText: string;
}

export function isDocumentDirty(document: LocalJavaDocument): boolean {
  return document.sourceText !== document.baselineText;
}

export function createEmptyDocument(): LocalJavaDocument {
  return {
    fileName: null,
    sourceText: "",
    baselineText: "",
  };
}
