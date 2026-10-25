import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DiagnosticsPanel } from "@/components/diagnostics/DiagnosticsPanel";
import { uiText } from "@/shared/i18n/ru";
import type { WorkspaceInspectResponse } from "@/shared/types/workspace";

const sampleResult: WorkspaceInspectResponse = {
  parse: {
    status: "syntax_errors",
    has_syntax_errors: true,
    diagnostics: [
      {
        severity: "error",
        code: "java.syntax_error",
        message: "Синтаксическая ошибка в исходном тексте Java.",
        start_line: 1,
        start_column: 10,
        end_line: 1,
        end_column: 11,
        start_byte: 9,
        end_byte: 10,
      },
    ],
    root: {
      type: "program",
      start_byte: 0,
      end_byte: 10,
      start_line: 1,
      start_column: 1,
      end_line: 1,
      end_column: 11,
      child_count: 1,
    },
    source_byte_length: 10,
    coordinate_system: "line_utf16_column_1_based_half_open",
    grammar: "tree-sitter-java",
  },
  scratch: {
    method_name: null,
    method_ir_id: null,
    blocks: [],
    root_block_ids: [],
  },
  blocks: [],
  ir_summary: {
    node_count: 1,
    class_names: [],
    method_names: [],
    unsupported_count: 0,
  },
  static_diagnostics: [],
  quick_fixes: [],
  metrics: {},
  llm_configured: false,
  logical_review: null,
  logical_error_count: 0,
  source_hash: "abc",
  coordinate_system: "line_utf16_column_1_based_half_open",
};

describe("DiagnosticsPanel", () => {
  it("показывает idle и loading", () => {
    const { rerender } = render(
      <DiagnosticsPanel workspaceState={{ kind: "idle" }} onReveal={vi.fn()} />,
    );
    expect(screen.getByText(uiText.diagnosticsIdle)).toBeInTheDocument();
    rerender(
      <DiagnosticsPanel workspaceState={{ kind: "loading" }} onReveal={vi.fn()} />,
    );
    expect(screen.getByText(uiText.diagnosticsLoading)).toBeInTheDocument();
  });

  it("показывает успешный разбор без ошибок", () => {
    render(
      <DiagnosticsPanel
        workspaceState={{
          kind: "success",
          result: {
            ...sampleResult,
            parse: { ...sampleResult.parse, status: "ok", has_syntax_errors: false, diagnostics: [] },
          },
          sourceFingerprint: "x",
        }}
        onReveal={vi.fn()}
      />,
    );
    expect(screen.getByText(uiText.diagnosticsOk)).toBeInTheDocument();
  });

  it("показывает diagnostics и вызывает переход", async () => {
    const user = userEvent.setup();
    const onReveal = vi.fn();
    render(
      <DiagnosticsPanel
        workspaceState={{
          kind: "success_with_errors",
          result: sampleResult,
          sourceFingerprint: "x",
        }}
        onReveal={onReveal}
      />,
    );
    expect(screen.getByText(/java.syntax_error/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: uiText.diagnosticsGoTo }));
    expect(onReveal).toHaveBeenCalledWith(1, 10);
  });

  it("отправляет в LLM только выбранные ошибки", async () => {
    const user = userEvent.setup();
    const onRepair = vi.fn();
    render(
      <DiagnosticsPanel
        workspaceState={{
          kind: "success_with_errors",
          result: {
            ...sampleResult,
            parse: {
              ...sampleResult.parse,
              status: "ok",
              has_syntax_errors: false,
              diagnostics: [],
            },
            llm_configured: true,
            logical_error_count: 1,
            logical_review: {
              status: "ok",
              issues: [
                {
                  id: "issue_1",
                  severity: "error",
                  code: "llm.logic.eq",
                  title: "Сравнение",
                  message: "Нужен equals",
                  explanation: "объекты",
                  start_line: 2,
                  start_column: 1,
                  end_line: 2,
                  end_column: 10,
                  start_byte: 10,
                  end_byte: 20,
                  confidence: "high",
                  fix: null,
                  affects_execution: true,
                },
                {
                  id: "issue_2",
                  severity: "structure",
                  code: "llm.structure.long_method",
                  title: "Длинный метод",
                  message: "Слишком много строк",
                  explanation: "читаемость",
                  start_line: 5,
                  start_column: 1,
                  end_line: 40,
                  end_column: 2,
                  start_byte: 50,
                  end_byte: 400,
                  confidence: "medium",
                  fix: null,
                  affects_execution: false,
                },
              ],
              notes: [],
              model: "deepseek-chat",
              error_reason: null,
            },
          },
          sourceFingerprint: "x",
        }}
        onReveal={vi.fn()}
        onRepairWithLlm={onRepair}
      />,
    );
    expect(screen.getByText(new RegExp(uiText.diagnosticsErrors))).toBeInTheDocument();
    expect(screen.getByText(new RegExp(uiText.diagnosticsStructure))).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: `${uiText.diagnosticsRepairLlmSelected} (1)` }),
    );
    expect(onRepair).toHaveBeenCalledWith([
      expect.objectContaining({ id: "issue_1", severity: "error" }),
    ]);
  });
});
