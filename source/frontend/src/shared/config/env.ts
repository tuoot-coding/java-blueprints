/** Конфигурация Frontend из переменных окружения Next.js. */

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

function normalizeBaseUrl(rawValue: string): string {
  return rawValue.trim().replace(/\/+$/, "");
}

export function getApiBaseUrl(): string {
  const fromEnv = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (typeof fromEnv === "string" && fromEnv.trim().length > 0) {
    return normalizeBaseUrl(fromEnv);
  }
  return DEFAULT_API_BASE_URL;
}

/** Максимальный размер локально открываемого .java файла (байты, 4 МиБ). */
export const MAX_LOCAL_JAVA_FILE_BYTES = 4_194_304;

/** Интервал опроса health endpoint (мс). */
export const HEALTH_POLL_INTERVAL_MS = 10_000;
