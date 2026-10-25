import { getApiBaseUrl } from "@/shared/config/env";

export class ApiClientError extends Error {
  readonly statusCode?: number;
  readonly requestId?: string;
  readonly errorCode?: string;

  constructor(
    message: string,
    options?: { statusCode?: number; requestId?: string; errorCode?: string },
  ) {
    super(message);
    this.name = "ApiClientError";
    this.statusCode = options?.statusCode;
    this.requestId = options?.requestId;
    this.errorCode = options?.errorCode;
  }
}

export interface ApiRequestOptions {
  signal?: AbortSignal;
  requestId?: string;
  /** Таймаут запроса в мс. При превышении AbortError -> ApiClientError. */
  timeoutMs?: number;
}

const CSRF_COOKIE_NAME = "jb_csrf";
const CSRF_HEADER = "X-CSRF-Token";

export function readCsrfToken(): string | null {
  if (typeof document === "undefined") {
    return null;
  }
  const encoded = document.cookie
    .split("; ")
    .find((part) => part.startsWith(`${CSRF_COOKIE_NAME}=`))
    ?.slice(CSRF_COOKIE_NAME.length + 1);
  if (!encoded) {
    return null;
  }
  try {
    return decodeURIComponent(encoded);
  } catch {
    return encoded;
  }
}

async function apiRequestJson<T>(
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE",
  path: string,
  options: ApiRequestOptions & { body?: unknown } = {},
): Promise<T> {
  const baseUrl = getApiBaseUrl();
  const url = `${baseUrl}${path.startsWith("/") ? path : `/${path}`}`;
  const headers = new Headers({ Accept: "application/json" });
  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  if (options.requestId) {
    headers.set("X-Request-ID", options.requestId);
  }
  if (method !== "GET") {
    const csrf = readCsrfToken();
    if (csrf) {
      headers.set(CSRF_HEADER, csrf);
    }
  }

  const timeoutMs = options.timeoutMs;
  const timeoutController =
    timeoutMs != null && timeoutMs > 0 ? new AbortController() : null;
  const timeoutId =
    timeoutController != null
      ? window.setTimeout(() => timeoutController.abort(), timeoutMs)
      : null;
  const signal = mergeAbortSignals(options.signal, timeoutController?.signal);

  let response: Response;
  try {
    response = await fetch(url, {
      method,
      headers,
      signal,
      cache: "no-store",
      credentials: "include",
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
  } catch (error) {
    if (timeoutId != null) {
      window.clearTimeout(timeoutId);
    }
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiClientError(
        timeoutController?.signal.aborted
          ? `Превышено время ожидания Backend (${timeoutMs} мс)`
          : "Запрос отменен",
      );
    }
    const detail = error instanceof Error ? error.message : "network error";
    throw new ApiClientError(`Нет соединения с Backend (${baseUrl}): ${detail}`);
  }
  if (timeoutId != null) {
    window.clearTimeout(timeoutId);
  }

  const requestId = response.headers.get("X-Request-ID") ?? undefined;

  if (!response.ok) {
    let message = `Backend ответил HTTP ${response.status}`;
    let errorCode: string | undefined;
    try {
      const payload = (await response.json()) as {
        message?: unknown;
        error_code?: unknown;
      };
      if (typeof payload.message === "string" && payload.message.length > 0) {
        message = payload.message;
      }
      if (typeof payload.error_code === "string") {
        errorCode = payload.error_code;
      }
    } catch {
      // тело ошибки может отсутствовать
    }
    throw new ApiClientError(message, {
      statusCode: response.status,
      requestId,
      errorCode,
    });
  }

  if (response.status === 204) {
    return undefined as T;
  }

  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiClientError("Ответ Backend не является JSON", {
      statusCode: response.status,
      requestId,
    });
  }
}

export async function apiGetJson<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  return apiRequestJson<T>("GET", path, options);
}

export async function apiPostJson<T>(
  path: string,
  body: unknown,
  options: ApiRequestOptions = {},
): Promise<T> {
  return apiRequestJson<T>("POST", path, { ...options, body });
}

export async function apiPatchJson<T>(
  path: string,
  body: unknown,
  options: ApiRequestOptions = {},
): Promise<T> {
  return apiRequestJson<T>("PATCH", path, { ...options, body });
}

function mergeAbortSignals(
  primary: AbortSignal | undefined,
  secondary: AbortSignal | undefined,
): AbortSignal | undefined {
  if (primary == null) {
    return secondary;
  }
  if (secondary == null) {
    return primary;
  }
  if (typeof AbortSignal.any === "function") {
    return AbortSignal.any([primary, secondary]);
  }
  const merged = new AbortController();
  const abortMerged = () => merged.abort();
  if (primary.aborted || secondary.aborted) {
    merged.abort();
    return merged.signal;
  }
  primary.addEventListener("abort", abortMerged, { once: true });
  secondary.addEventListener("abort", abortMerged, { once: true });
  return merged.signal;
}
