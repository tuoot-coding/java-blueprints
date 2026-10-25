"use client";

import { useCallback, useRef, useState } from "react";

import { uiText } from "@/shared/i18n/ru";
import { downloadLocalJavaFile, readLocalJavaFile } from "@/shared/lib/javaFile";
import {
  createEmptyDocument,
  isDocumentDirty,
  type LocalJavaDocument,
} from "@/shared/types/editor";

export interface LocalJavaDocumentApi {
  document: LocalJavaDocument;
  dirty: boolean;
  errorMessage: string | null;
  setSourceText: (text: string) => void;
  openFile: (file: File) => Promise<void>;
  saveLocalCopy: () => void;
  clearError: () => void;
}

export function useLocalJavaDocument(): LocalJavaDocumentApi {
  const [document, setDocument] = useState<LocalJavaDocument>(createEmptyDocument);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const documentRef = useRef(document);
  documentRef.current = document;

  const setSourceText = useCallback((text: string) => {
    setDocument((current) => ({ ...current, sourceText: text }));
  }, []);

  const openFile = useCallback(async (file: File) => {
    const current = documentRef.current;
    if (isDocumentDirty(current)) {
      const confirmed = window.confirm(uiText.discardChangesConfirm);
      if (!confirmed) {
        return;
      }
    }

    try {
      const loaded = await readLocalJavaFile(file);
      setDocument({
        fileName: loaded.fileName,
        sourceText: loaded.text,
        baselineText: loaded.text,
      });
      setErrorMessage(null);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : uiText.fileReadError);
    }
  }, []);

  const saveLocalCopy = useCallback(() => {
    const current = documentRef.current;
    const name = current.fileName ?? "Main.java";
    downloadLocalJavaFile(name, current.sourceText);
    setDocument((prev) => ({ ...prev, baselineText: prev.sourceText, fileName: name }));
  }, []);

  const clearError = useCallback(() => {
    setErrorMessage(null);
  }, []);

  return {
    document,
    dirty: isDocumentDirty(document),
    errorMessage,
    setSourceText,
    openFile,
    saveLocalCopy,
    clearError,
  };
}
