"use client";

import { useCallback, useRef, useState } from "react";

import { ApiClientError } from "@/shared/api/client";
import { inspectWorkspace } from "@/shared/api/workspace";
import { fingerprintSource } from "@/shared/lib/sourceFingerprint";
import type { WorkspaceUiState } from "@/shared/types/workspace";

export { fingerprintSource };

export interface UseWorkspaceInspectApi {
  state: WorkspaceUiState;
  runInspect: (source: string) => Promise<void>;
  clearResult: () => void;
  invalidateOnSourceChange: (source: string) => void;
}

export function useWorkspaceInspect(): UseWorkspaceInspectApi {
  const [state, setState] = useState<WorkspaceUiState>({ kind: "idle" });
  const requestSerialRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);

  const clearResult = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    requestSerialRef.current += 1;
    setState({ kind: "idle" });
  }, []);

  const invalidateOnSourceChange = useCallback((source: string) => {
    setState((current) => {
      if (current.kind === "idle" || current.kind === "loading") {
        return current;
      }
      if (current.sourceFingerprint === fingerprintSource(source)) {
        return current;
      }
      return { kind: "idle" };
    });
  }, []);

  const runInspect = useCallback(async (source: string) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const serial = requestSerialRef.current + 1;
    requestSerialRef.current = serial;
    const sourceFingerprint = fingerprintSource(source);
    setState({ kind: "loading" });

    try {
      const result = await inspectWorkspace(source, {
        signal: controller.signal,
        includeLlm: true,
      });
      if (serial !== requestSerialRef.current) {
        return;
      }
      // success_with_errors только при синтаксисе или LLM-ошибках, влияющих на выполнение.
      const criticalLlm = (result.logical_review?.issues ?? []).some(
        (item) => item.affects_execution !== false && item.severity === "error",
      );
      const hasErrors = result.parse.has_syntax_errors || criticalLlm;
      setState({
        kind: hasErrors ? "success_with_errors" : "success",
        result,
        sourceFingerprint,
      });
    } catch (error) {
      if (controller.signal.aborted || serial !== requestSerialRef.current) {
        return;
      }
      const message =
        error instanceof ApiClientError
          ? error.message
          : error instanceof Error
            ? error.message
            : "Ошибка запроса Workspace";
      setState({ kind: "request_error", message, sourceFingerprint });
    }
  }, []);

  return { state, runInspect, clearResult, invalidateOnSourceChange };
}
