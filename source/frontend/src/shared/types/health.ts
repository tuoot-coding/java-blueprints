/** Типы ответа GET /api/v1/health по contracts/openapi.json. */

export type HealthStatus = "ok";

export interface HealthResponse {
  status: HealthStatus;
  service: string;
  version: string;
  started_at: string;
  checked_at: string;
  uptime_seconds: number;
}

export type BackendConnectionState =
  | { kind: "checking" }
  | { kind: "ok"; health: HealthResponse }
  | { kind: "error"; message: string; statusCode?: number };
