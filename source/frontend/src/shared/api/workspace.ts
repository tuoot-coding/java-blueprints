import { apiPostJson, type ApiRequestOptions } from "@/shared/api/client";
import type {
  ApplyLogicFixResponse,
  GenerateFromSchemeResponse,
  LlmSuggestedFix,
  RepairIssueInput,
  RepairWithLlmResponse,
  ScratchProgram,
  WorkspaceInspectResponse,
} from "@/shared/types/workspace";

export const WORKSPACE_INSPECT_PATH = "/api/v1/workspace/inspect";
export const WORKSPACE_APPLY_LOGIC_FIX_PATH = "/api/v1/workspace/apply-logic-fix";
export const WORKSPACE_REPAIR_WITH_LLM_PATH = "/api/v1/workspace/repair-with-llm";
export const WORKSPACE_GENERATE_FROM_SCHEME_PATH = "/api/v1/workspace/generate-from-scheme";

export async function inspectWorkspace(
  source: string,
  options: ApiRequestOptions & { includeLlm?: boolean } = {},
): Promise<WorkspaceInspectResponse> {
  const { includeLlm = true, ...requestOptions } = options;
  return apiPostJson<WorkspaceInspectResponse>(
    WORKSPACE_INSPECT_PATH,
    { source, include_llm: includeLlm },
    requestOptions,
  );
}

export async function applyLogicFix(
  payload: {
    source: string;
    source_hash: string;
    issue_id: string;
    fix: LlmSuggestedFix;
  },
  options: ApiRequestOptions = {},
): Promise<ApplyLogicFixResponse> {
  return apiPostJson<ApplyLogicFixResponse>(
    WORKSPACE_APPLY_LOGIC_FIX_PATH,
    {
      source: payload.source,
      source_hash: payload.source_hash,
      issue_id: payload.issue_id,
      start_byte: payload.fix.start_byte,
      end_byte: payload.fix.end_byte,
      expected_snippet: payload.fix.expected_snippet,
      replacement: payload.fix.replacement,
    },
    options,
  );
}

/** Repair / генерация через GigaChat может занимать минуты. */
export const REPAIR_REQUEST_TIMEOUT_MS = 180_000;

export async function repairWithLlm(
  payload: {
    source: string;
    source_hash: string;
    issues: RepairIssueInput[];
  },
  options: ApiRequestOptions = {},
): Promise<RepairWithLlmResponse> {
  return apiPostJson<RepairWithLlmResponse>(
    WORKSPACE_REPAIR_WITH_LLM_PATH,
    {
      source: payload.source,
      source_hash: payload.source_hash,
      issues: payload.issues,
    },
    { timeoutMs: REPAIR_REQUEST_TIMEOUT_MS, ...options },
  );
}

export async function generateFromScheme(
  payload: {
    source: string;
    source_hash: string;
    scratch: ScratchProgram;
  },
  options: ApiRequestOptions = {},
): Promise<GenerateFromSchemeResponse> {
  return apiPostJson<GenerateFromSchemeResponse>(
    WORKSPACE_GENERATE_FROM_SCHEME_PATH,
    {
      source: payload.source,
      source_hash: payload.source_hash,
      scratch: payload.scratch,
    },
    { timeoutMs: REPAIR_REQUEST_TIMEOUT_MS, ...options },
  );
}
