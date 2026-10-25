import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchBackendHealth } from "@/shared/api/health";

describe("fetchBackendHealth", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("возвращает HealthResponse при корректном JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        headers: new Headers({ "X-Request-ID": "test-id" }),
        json: async () => ({
          status: "ok",
          service: "java-blueprints-backend",
          version: "0.1.0",
          started_at: "2026-10-23T20:00:00Z",
          checked_at: "2026-10-23T20:00:01Z",
          uptime_seconds: 1.5,
        }),
      }),
    );

    const health = await fetchBackendHealth();
    expect(health.status).toBe("ok");
    expect(health.version).toBe("0.1.0");
  });

  it("отклоняет ответ с неверной структурой", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        headers: new Headers(),
        json: async () => ({ status: "weird" }),
      }),
    );

    await expect(fetchBackendHealth()).rejects.toThrow(/контракту/);
  });
});
