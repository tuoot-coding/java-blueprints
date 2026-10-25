import { apiPostJson, type ApiRequestOptions } from "@/shared/api/client";
import type { ParseJavaResponse } from "@/shared/types/parser";

const PARSE_PATH = "/api/v1/parser/parse";

function isParseJavaResponse(value: unknown): value is ParseJavaResponse {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const record = value as Record<string, unknown>;
  return (
    (record.status === "ok" || record.status === "syntax_errors") &&
    typeof record.has_syntax_errors === "boolean" &&
    Array.isArray(record.diagnostics) &&
    typeof record.root === "object" &&
    record.root !== null &&
    typeof record.source_byte_length === "number" &&
    record.coordinate_system === "line_utf16_column_1_based_half_open" &&
    typeof record.grammar === "string"
  );
}

export async function parseJavaSource(
  source: string,
  options: ApiRequestOptions = {},
): Promise<ParseJavaResponse> {
  const payload = await apiPostJson<unknown>(PARSE_PATH, { source }, options);
  if (!isParseJavaResponse(payload)) {
    throw new Error("Ответ /api/v1/parser/parse не соответствует контракту");
  }
  return payload;
}

export { PARSE_PATH };
