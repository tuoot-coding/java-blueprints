import { apiGetJson, type ApiRequestOptions } from "@/shared/api/client";
import type { HealthResponse } from "@/shared/types/health";

const HEALTH_PATH = "/api/v1/health";

function isHealthResponse(value: unknown): value is HealthResponse {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const record = value as Record<string, unknown>;
  return (
    record.status === "ok" &&
    typeof record.service === "string" &&
    typeof record.version === "string" &&
    typeof record.started_at === "string" &&
    typeof record.checked_at === "string" &&
    typeof record.uptime_seconds === "number"
  );
}

export async function fetchBackendHealth(
  options: ApiRequestOptions = {},
): Promise<HealthResponse> {
  const payload = await apiGetJson<unknown>(HEALTH_PATH, options);
  if (!isHealthResponse(payload)) {
    throw new Error("Ответ /api/v1/health не соответствует контракту");
  }
  return payload;
}
