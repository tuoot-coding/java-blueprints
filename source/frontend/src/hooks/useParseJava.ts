"use client";

import { useCallback, useRef, useState } from "react";

import { ApiClientError } from "@/shared/api/client";
import { parseJavaSource } from "@/shared/api/parser";
import { fingerprintSource } from "@/shared/lib/sourceFingerprint";
import type { ParseUiState } from "@/shared/types/parser";

export { fingerprintSource };

export interface UseParseJavaApi {
  parseState: ParseUiState;
  runParse: (source: string) => Promise<void>;
  clearParseResult: () => void;
  invalidateOnSourceChange: (source: string) => void;
}

export function useParseJava(): UseParseJavaApi {
  const [parseState, setParseState] = useState<ParseUiState>({ kind: "idle" });
  const requestSerialRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);

  const clearParseResult = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    requestSerialRef.current += 1;
    setParseState({ kind: "idle" });
  }, []);

  const invalidateOnSourceChange = useCallback((source: string) => {
    setParseState((current) => {
      if (current.kind === "idle" || current.kind === "loading") {
        return current;
      }
      if (current.sourceFingerprint === fingerprintSource(source)) {
        return current;
      }
      return { kind: "idle" };
    });
  }, []);

  const runParse = useCallback(async (source: string) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const serial = requestSerialRef.current + 1;
    requestSerialRef.current = serial;
    const sourceFingerprint = fingerprintSource(source);
    setParseState({ kind: "loading" });

    try {
      const result = await parseJavaSource(source, { signal: controller.signal });
      if (serial !== requestSerialRef.current) {
        return;
      }
      if (result.has_syntax_errors) {
        setParseState({ kind: "success_with_errors", result, sourceFingerprint });
      } else {
        setParseState({ kind: "success", result, sourceFingerprint });
      }
    } catch (error) {
      if (controller.signal.aborted || serial !== requestSerialRef.current) {
        return;
      }
      const message =
        error instanceof ApiClientError
          ? error.message
          : error instanceof Error
            ? error.message
            : "Ошибка запроса Parser";
      setParseState({ kind: "request_error", message, sourceFingerprint });
    }
  }, []);

  return { parseState, runParse, clearParseResult, invalidateOnSourceChange };
}
