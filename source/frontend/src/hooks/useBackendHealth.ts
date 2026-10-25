"use client";

import { useEffect, useState } from "react";

import { ApiClientError } from "@/shared/api/client";
import { fetchBackendHealth } from "@/shared/api/health";
import { HEALTH_POLL_INTERVAL_MS } from "@/shared/config/env";
import type { BackendConnectionState } from "@/shared/types/health";

export function useBackendHealth(): BackendConnectionState {
  const [state, setState] = useState<BackendConnectionState>({ kind: "checking" });

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();

    async function poll(): Promise<void> {
      try {
        const health = await fetchBackendHealth({ signal: controller.signal });
        if (!cancelled) {
          setState({ kind: "ok", health });
        }
      } catch (error) {
        if (cancelled || controller.signal.aborted) {
          return;
        }
        const message =
          error instanceof ApiClientError
            ? error.message
            : error instanceof Error
              ? error.message
              : "Неизвестная ошибка соединения";
        const statusCode = error instanceof ApiClientError ? error.statusCode : undefined;
        setState({ kind: "error", message, statusCode });
      }
    }

    void poll();
    const timerId = window.setInterval(() => {
      void poll();
    }, HEALTH_POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      controller.abort();
      window.clearInterval(timerId);
    };
  }, []);

  return state;
}
