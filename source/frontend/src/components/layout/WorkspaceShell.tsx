"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { AuthDialog } from "@/components/auth/AuthDialog";
import { CabinetDialog } from "@/components/auth/CabinetDialog";
import {
  CodeComparePanel,
  type RepairCompareState,
} from "@/components/compare/CodeComparePanel";
import { SchemeFlowCompare } from "@/components/compare/SchemeFlowCompare";
import { DiagnosticsPanel } from "@/components/diagnostics/DiagnosticsPanel";
import { JavaEditor } from "@/components/editor/JavaEditor";
import { ProjectExplorer } from "@/components/explorer/ProjectExplorer";
import { GraphWorkspace } from "@/components/graph/GraphWorkspace";
import { PropertiesInspector } from "@/components/inspector/PropertiesInspector";
import { ResizableSplit } from "@/components/layout/ResizableSplit";
import { StatusBar } from "@/components/layout/StatusBar";
import {
  CompareResultsToast,
  type CompareToastState,
} from "@/components/testing/CompareResultsToast";
import { HeaderToolbar } from "@/components/toolbar/HeaderToolbar";
import { useAuthSession } from "@/hooks/useAuthSession";
import { useBackendHealth } from "@/hooks/useBackendHealth";
import { useLocalJavaDocument } from "@/hooks/useLocalJavaDocument";
import { useUiTheme } from "@/hooks/useUiTheme";
import { fingerprintSource, useWorkspaceInspect } from "@/hooks/useWorkspaceInspect";
import { ApiClientError } from "@/shared/api/client";
import { applyLogicFix, generateFromScheme, repairWithLlm } from "@/shared/api/workspace";
import { uiText } from "@/shared/i18n/ru";
import { downloadLocalJavaFile } from "@/shared/lib/javaFile";
import {
  findProjectFile,
  readProjectFromFileList,
  type ProjectFileEntry,
} from "@/shared/lib/projectTree";
import {
  BLANK_SCHEME_JAVA,
  createBlankScratchProgram,
  schemeStructureKey,
} from "@/shared/lib/schemeEdit";
import {
  canUndoScheme,
  createSchemeHistory,
  pushSchemeHistory,
  resetSchemeHistory,
  undoSchemeHistory,
  type SchemeHistoryState,
} from "@/shared/lib/schemeHistory";
import { buildSchemeMarkers } from "@/shared/lib/schemeMarkers";
import type { SyntaxDiagnostic } from "@/shared/types/parser";
import type { LlmIssue, ScratchProgram } from "@/shared/types/workspace";

export function WorkspaceShell() {
  const connection = useBackendHealth();
  const { preference: themePreference, resolved: resolvedTheme, setTheme } = useUiTheme();
  const auth = useAuthSession();
  const [authDialogOpen, setAuthDialogOpen] = useState(false);
  const [cabinetOpen, setCabinetOpen] = useState(false);
  const { document, dirty, errorMessage, setSourceText, openFile, saveLocalCopy, clearError } =
    useLocalJavaDocument();
  const { state, runInspect, clearResult, invalidateOnSourceChange } = useWorkspaceInspect();
  const [revealPosition, setRevealPosition] = useState<{ line: number; column: number } | null>(
    null,
  );
  const [selectedBlockId, setSelectedBlockId] = useState<string | null>(null);
  const [applyBusyIssueId, setApplyBusyIssueId] = useState<string | null>(null);
  const [repairBusy, setRepairBusy] = useState(false);
  const [schemeBusy, setSchemeBusy] = useState(false);
  const [fixError, setFixError] = useState<string | null>(null);
  const [editorCollapsed, setEditorCollapsed] = useState(false);
  const [compare, setCompare] = useState<RepairCompareState | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [editedScratch, setEditedScratch] = useState<ScratchProgram | null>(null);
  const [schemeBaseline, setSchemeBaseline] = useState<ScratchProgram | null>(null);
  const [schemeDirty, setSchemeDirty] = useState(false);
  const [schemeHistory, setSchemeHistory] = useState<SchemeHistoryState>(() =>
    createSchemeHistory(null),
  );
  const [graphCollapsed, setGraphCollapsed] = useState(false);
  const [graphFullscreen, setGraphFullscreen] = useState(false);
  const [schemeCompareCollapsed, setSchemeCompareCollapsed] = useState(false);
  const [codeCompareCollapsed, setCodeCompareCollapsed] = useState(false);
  const [compareToast, setCompareToast] = useState<CompareToastState | null>(null);
  const [projectName, setProjectName] = useState<string | null>(null);
  const [projectFiles, setProjectFiles] = useState<ProjectFileEntry[]>([]);
  const [activeFilePath, setActiveFilePath] = useState<string | null>(null);
  const repairAbortRef = useRef<AbortController | null>(null);

  const fingerprint = fingerprintSource(document.sourceText);
  const resultFresh =
    (state.kind === "success" || state.kind === "success_with_errors") &&
    state.sourceFingerprint === fingerprint
      ? state.result
      : null;

  const activeScratch = editedScratch ?? resultFresh?.scratch ?? null;

  const schemeMarkers = useMemo(
    () =>
      buildSchemeMarkers(activeScratch, {
        syntax: resultFresh?.parse.diagnostics,
        staticItems: resultFresh?.static_diagnostics,
        llmIssues: resultFresh?.logical_review?.issues,
      }),
    [activeScratch, resultFresh],
  );

  useEffect(() => {
    // Подхватываем схему с сервера только после inspect; локальную blank не затираем.
    if (resultFresh?.scratch) {
      setEditedScratch(resultFresh.scratch);
      setSchemeBaseline(resultFresh.scratch);
      setSchemeHistory(resetSchemeHistory(resultFresh.scratch));
      setSchemeDirty(false);
      setEditMode(false);
    }
  }, [resultFresh?.source_hash]);

  function handleCreateBlankScheme() {
    const blank = createBlankScratchProgram("process");
    setCompare(null);
    setEditedScratch(blank);
    setSchemeBaseline(blank);
    setSchemeHistory(resetSchemeHistory(blank));
    setSchemeDirty(true);
    setEditMode(true);
    setGraphCollapsed(false);
    setSelectedBlockId(blank.blocks[0]?.id ?? null);
    if (!document.sourceText.trim()) {
      setSourceText(BLANK_SCHEME_JAVA);
    }
  }

  function handleScratchChange(next: ScratchProgram) {
    setEditedScratch(next);
    setSchemeDirty(true);
    setSchemeHistory((history) => pushSchemeHistory(history, next));
  }

  function handleUndoScheme() {
    setSchemeHistory((history) => {
      const result = undoSchemeHistory(history);
      if (result.program) {
        setEditedScratch(result.program);
        setSchemeDirty(
          schemeBaseline != null &&
            schemeStructureKey(result.program) !== schemeStructureKey(schemeBaseline),
        );
      }
      return result.state;
    });
  }

  function offerSaveCodeAsSeparateFile() {
    if (!document.sourceText.trim()) {
      return;
    }
    const confirmed = window.confirm(uiText.graphExitSaveCodeConfirm);
    if (!confirmed) {
      return;
    }
    const suggested =
      (document.fileName?.replace(/\.java$/i, "") || "Main") + ".edited.java";
    const name = window.prompt(uiText.editorSaveAsPrompt, suggested);
    if (!name) {
      return;
    }
    downloadLocalJavaFile(name, document.sourceText);
  }

  function handleExitConstructorWithoutSave() {
    if (schemeDirty) {
      const confirmed = window.confirm(uiText.graphExitDiscardConfirm);
      if (!confirmed) {
        return;
      }
    }
    const restore = schemeBaseline ?? resultFresh?.scratch ?? null;
    setEditedScratch(restore);
    setSchemeHistory(resetSchemeHistory(restore));
    setSchemeDirty(false);
    setEditMode(false);
    offerSaveCodeAsSeparateFile();
  }

  function handleToggleEdit() {
    if (editMode) {
      // Выход из конструктора: спросить про отмену правок схемы и сохранение кода.
      if (schemeDirty) {
        const discard = window.confirm(uiText.graphExitDiscardConfirm);
        if (!discard) {
          return;
        }
        const restore = schemeBaseline ?? resultFresh?.scratch ?? null;
        setEditedScratch(restore);
        setSchemeHistory(resetSchemeHistory(restore));
        setSchemeDirty(false);
      }
      setEditMode(false);
      offerSaveCodeAsSeparateFile();
      return;
    }
    const baseline = editedScratch ?? resultFresh?.scratch ?? null;
    setSchemeBaseline(baseline);
    setSchemeHistory(resetSchemeHistory(baseline));
    setEditMode(true);
    setGraphCollapsed(false);
  }

  async function handleOpenProject(list: FileList) {
    try {
      const entries = await readProjectFromFileList(list);
      if (entries.length === 0) {
        setFixError(uiText.explorerNoJavaInProject);
        return;
      }
      const firstPath = entries[0]!.path;
      const rootName = firstPath.includes("/") ? firstPath.split("/")[0]! : uiText.explorerTitle;
      setProjectName(rootName);
      setProjectFiles(entries);
      const first = entries[0]!;
      setActiveFilePath(first.path);
      clearResult();
      setSelectedBlockId(null);
      setCompare(null);
      setFixError(null);
      await openFile(new File([first.text], first.name, { type: "text/x-java-source" }));
    } catch (error) {
      setFixError(toErrorMessage(error, uiText.fileReadError));
    }
  }

  function handleOpenProjectFile(path: string) {
    const entry = findProjectFile(projectFiles, path);
    if (!entry) {
      return;
    }
    setActiveFilePath(path);
    clearResult();
    setSelectedBlockId(null);
    setCompare(null);
    void openFile(new File([entry.text], entry.name, { type: "text/x-java-source" }));
  }

  function handleSaveCodeAs() {
    if (!document.sourceText.trim()) {
      return;
    }
    const suggested =
      (document.fileName?.replace(/\.java$/i, "") || "Main") + ".edited.java";
    const name = window.prompt(uiText.editorSaveAsPrompt, suggested);
    if (!name) {
      return;
    }
    downloadLocalJavaFile(name, document.sourceText);
  }

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape" && graphFullscreen) {
        setGraphFullscreen(false);
      }
      const isUndo =
        (event.ctrlKey || event.metaKey) &&
        !event.shiftKey &&
        event.key.toLowerCase() === "z";
      if (isUndo && editMode) {
        event.preventDefault();
        handleUndoScheme();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [graphFullscreen, editMode, schemeBaseline]);

  // В редакторе красным только реальные синтаксические ошибки парсера.
  // Структура / LLM остаются в правой панели, без ложной подсветки валидного Java.
  const activeDiagnostics = useMemo(() => {
    if (!resultFresh) {
      return [] as SyntaxDiagnostic[];
    }
    return resultFresh.parse.diagnostics.filter(
      (item) => item.severity === "error" || item.severity === "ERROR",
    );
  }, [resultFresh]);

  const panelState =
    state.kind === "success" || state.kind === "success_with_errors"
      ? state.sourceFingerprint === fingerprint
        ? state
        : { kind: "idle" as const }
      : state;

  async function handleApplyLogicFix(issue: LlmIssue) {
    if (!resultFresh || !issue.fix) {
      return;
    }
    const confirmed = window.confirm(
      `${uiText.diagnosticsFixConfirm}\n\n${issue.title}\n${issue.fix.title}`,
    );
    if (!confirmed) {
      return;
    }
    setFixError(null);
    setApplyBusyIssueId(issue.id);
    try {
      const response = await applyLogicFix({
        source: document.sourceText,
        source_hash: resultFresh.source_hash,
        issue_id: issue.id,
        fix: issue.fix,
      });
      setCompare(null);
      setSourceText(response.source);
      await runInspect(response.source);
    } catch (error) {
      setFixError(toErrorMessage(error, uiText.diagnosticsFixFailed));
    } finally {
      setApplyBusyIssueId(null);
    }
  }

  async function handleRepairWithLlm(
    issues: Array<{
      id: string;
      severity: string;
      code: string;
      title: string;
      message: string;
      start_line: number;
      end_line: number;
    }>,
  ) {
    if (!resultFresh || repairBusy) {
      return;
    }
    if (issues.length === 0) {
      setFixError(uiText.diagnosticsRepairLlmNeedIssues);
      return;
    }
    const confirmed = window.confirm(
      `${uiText.diagnosticsRepairLlmConfirm} (${issues.length})`,
    );
    if (!confirmed) {
      return;
    }

    repairAbortRef.current?.abort();
    const controller = new AbortController();
    repairAbortRef.current = controller;
    const originalSnapshot = document.sourceText;
    setFixError(null);
    setRepairBusy(true);
    try {
      const response = await repairWithLlm(
        {
          source: originalSnapshot,
          source_hash: resultFresh.source_hash,
          issues,
        },
        { signal: controller.signal },
      );
      if (controller.signal.aborted) {
        return;
      }
      if (response.status !== "ok" || !response.source) {
        setFixError(
          response.error_reason
            ? `${uiText.diagnosticsRepairLlmFailed}: ${response.status} (${response.error_reason})`
            : `${uiText.diagnosticsRepairLlmFailed}: ${response.status}`,
        );
        return;
      }
      setSchemeCompareCollapsed(false);
      setCodeCompareCollapsed(false);
      setCompare({
        originalSource: originalSnapshot,
        repairedSource: response.source,
        fixedIssueIds: response.fixed_issue_ids ?? [],
        notes: response.notes ?? [],
        testCompare: response.test_compare ?? null,
        codeCompare: response.code_compare ?? null,
        originalScratch: response.original_scratch ?? null,
        generatedScratch: response.generated_scratch ?? null,
      });
      setEditorCollapsed(false);
      setGraphCollapsed(false);
      if (response.code_compare) {
        setCompareToast({
          codeCompare: response.code_compare,
          testCompare: response.test_compare ?? null,
        });
      }
    } catch (error) {
      if (controller.signal.aborted) {
        return;
      }
      setFixError(toErrorMessage(error, uiText.diagnosticsRepairLlmFailed));
    } finally {
      if (repairAbortRef.current === controller) {
        repairAbortRef.current = null;
      }
      setRepairBusy(false);
    }
  }

  async function handleSaveScheme() {
    if (!resultFresh || !editedScratch || schemeBusy) {
      return;
    }
    const confirmed = window.confirm(uiText.graphSaveConfirm);
    if (!confirmed) {
      return;
    }
    setFixError(null);
    setSchemeBusy(true);
    const originalSnapshot = document.sourceText;
    try {
      const response = await generateFromScheme({
        source: originalSnapshot,
        source_hash: resultFresh.source_hash,
        scratch: editedScratch,
      });
      if (response.status !== "ok" || !response.source) {
        setFixError(
          response.error_reason
            ? `${uiText.graphSaveFailed}: ${response.status} (${response.error_reason})`
            : `${uiText.graphSaveFailed}: ${response.status}`,
        );
        return;
      }
      // Не пишем в редактор сразу - только сравнение и запрос разрешения на замену.
      setSchemeDirty(false);
      setEditMode(false);
      setSchemeCompareCollapsed(false);
      setCodeCompareCollapsed(false);
      setCompare({
        originalSource: originalSnapshot,
        repairedSource: response.source,
        fixedIssueIds: response.modules_written ?? [],
        notes: response.notes ?? [],
        testCompare: response.test_compare ?? null,
        codeCompare: response.code_compare ?? null,
        originalScratch: response.original_scratch ?? null,
        generatedScratch: response.generated_scratch ?? null,
      });
      setEditorCollapsed(false);
      setGraphCollapsed(false);
      if (response.code_compare) {
        setCompareToast({
          codeCompare: response.code_compare,
          testCompare: response.test_compare ?? null,
        });
      }
    } catch (error) {
      setFixError(toErrorMessage(error, uiText.graphSaveFailed));
    } finally {
      setSchemeBusy(false);
    }
  }

  async function acceptRepaired() {
    if (!compare) {
      return;
    }
    const allowed = window.confirm(uiText.graphReplaceConfirm);
    if (!allowed) {
      return;
    }
    const repaired = compare.repairedSource;
    setCompare(null);
    setEditorCollapsed(false);
    setSourceText(repaired);
    setFixError(null);
    try {
      await runInspect(repaired);
    } catch (error) {
      setFixError(toErrorMessage(error, uiText.diagnosticsRequestError));
    }
  }

  function discardRepaired() {
    setCompare(null);
    setEditorCollapsed(false);
  }

  function downloadRepaired() {
    if (!compare) {
      return;
    }
    const blob = new Blob([compare.repairedSource], { type: "text/x-java;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = window.document.createElement("a");
    const baseName = document.fileName?.replace(/\.java$/i, "") || "repaired";
    anchor.href = url;
    anchor.download = `${baseName}.repaired.java`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="flex h-screen min-h-0 flex-col bg-zinc-950 text-zinc-100">
      <HeaderToolbar
        fileName={document.fileName}
        dirty={dirty}
        themePreference={themePreference}
        onThemeChange={setTheme}
        parseBusy={
          state.kind === "loading" ||
          applyBusyIssueId !== null ||
          repairBusy ||
          schemeBusy
        }
        onOpenFile={(file) => {
          clearResult();
          setSelectedBlockId(null);
          setFixError(null);
          setCompare(null);
          setCompareToast(null);
          void openFile(file);
        }}
        onSaveLocal={saveLocalCopy}
        onSaveAs={handleSaveCodeAs}
        onParse={() => {
          // Временно: LLM / разбор / схема->код без обязательного входа.
          setFixError(null);
          void runInspect(document.sourceText);
        }}
        authLabel={
          auth.status === "authenticated" && auth.user
            ? auth.user.username
            : uiText.actionAuth
        }
        authHint={
          auth.status === "authenticated" ? uiText.actionCabinet : uiText.actionAuth
        }
        onAuthClick={() => {
          auth.setError(null);
          if (auth.status === "authenticated") {
            setCabinetOpen(true);
          } else {
            setAuthDialogOpen(true);
          }
        }}
      />

      {errorMessage || fixError || compare ? (
        <div
          className={`flex items-center justify-between border-b px-3 py-1.5 text-xs ${
            compare
              ? "border-sky-900/60 bg-sky-950/30 text-sky-200"
              : "border-red-900/60 bg-red-950/40 text-red-300"
          }`}
        >
          <span>
            {compare ? uiText.compareReady : (errorMessage ?? fixError)}
          </span>
          {!compare ? (
            <button
              type="button"
              className="rounded border border-red-800 px-2 py-0.5 hover:bg-red-900/40"
              onClick={() => {
                clearError();
                setFixError(null);
              }}
            >
              OK
            </button>
          ) : null}
        </div>
      ) : null}

      <div className="min-h-0 flex-1">
        <ResizableSplit
          orientation="vertical"
          storageKey="jb.split.main-right"
          initialRatio={0.78}
          minRatio={0.55}
          maxRatio={0.9}
          className="h-full"
          first={
            <ResizableSplit
              orientation="vertical"
              storageKey="jb.split.left-center"
              initialRatio={0.22}
              minRatio={0.12}
              maxRatio={0.4}
              className="h-full border-r border-zinc-800"
              first={
          <ProjectExplorer
            fileName={document.fileName}
            dirty={dirty}
            projectName={projectName}
            projectFiles={projectFiles}
            activeFilePath={activeFilePath}
            onOpenProject={(list) => {
              void handleOpenProject(list);
            }}
            onOpenProjectFile={handleOpenProjectFile}
            onClearProject={() => {
              setProjectName(null);
              setProjectFiles([]);
              setActiveFilePath(null);
            }}
          />
        }
              second={
                <ResizableSplit
                  orientation="horizontal"
                  storageKey="jb.split.graph-code"
                  initialRatio={0.62}
                  minRatio={0.2}
                  maxRatio={0.8}
                  className="h-full"
                  firstCollapsed={compare ? schemeCompareCollapsed : graphCollapsed}
                  secondCollapsed={compare ? codeCompareCollapsed : editorCollapsed}
                  first={
                    compare ? (
                      <SchemeFlowCompare
                        original={compare.originalScratch}
                        generated={compare.generatedScratch}
                        fillSlot
                        collapsed={schemeCompareCollapsed}
                        onToggleCollapsed={() => setSchemeCompareCollapsed((value) => !value)}
                      />
                    ) : (
                      <GraphWorkspace
                        scratch={activeScratch}
                        selectedBlockId={selectedBlockId}
                        editMode={editMode}
                        schemeDirty={schemeDirty}
                        saveBusy={schemeBusy}
                        collapsed={graphCollapsed}
                        fullscreen={graphFullscreen}
                        markers={schemeMarkers}
                        stale={
                          (state.kind === "success" || state.kind === "success_with_errors") &&
                          state.sourceFingerprint !== fingerprint
                        }
                        onSelectNode={(id, line, column) => {
                          setSelectedBlockId(id);
                          if (id && line != null && column != null) {
                            setRevealPosition({ line, column });
                          }
                        }}
                        onToggleEdit={handleToggleEdit}
                        onScratchChange={handleScratchChange}
                        onSaveScheme={() => {
                          void handleSaveScheme();
                        }}
                        onCreateBlankScheme={handleCreateBlankScheme}
                        canUndo={canUndoScheme(schemeHistory)}
                        onUndo={handleUndoScheme}
                        onExitWithoutSave={handleExitConstructorWithoutSave}
                        onToggleCollapsed={() => {
                          setGraphCollapsed((value) => !value);
                          if (!graphCollapsed) {
                            setGraphFullscreen(false);
                          }
                        }}
                        onToggleFullscreen={() => {
                          setGraphFullscreen((value) => {
                            const next = !value;
                            if (next) {
                              setGraphCollapsed(false);
                            }
                            return next;
                          });
                        }}
                      />
                    )
                  }
                  second={
                    compare ? (
                      <CodeComparePanel
                        compare={compare}
                        busy={repairBusy || schemeBusy || state.kind === "loading"}
                        collapsed={codeCompareCollapsed}
                        onToggleCollapsed={() => setCodeCompareCollapsed((value) => !value)}
                        onAccept={() => {
                          void acceptRepaired();
                        }}
                        onDiscard={discardRepaired}
                        onDownloadRepaired={downloadRepaired}
                      />
                    ) : (
                      <JavaEditor
                        value={document.sourceText}
                        collapsed={editorCollapsed}
                        onToggleCollapsed={() => setEditorCollapsed((value) => !value)}
                        onChange={(text) => {
                          setSourceText(text);
                          invalidateOnSourceChange(text);
                          setRevealPosition(null);
                        }}
                        diagnostics={activeDiagnostics}
                        revealPosition={revealPosition}
                        uiTheme={resolvedTheme}
                      />
                    )
                  }
                />
              }
            />
          }
          second={
            <aside className="flex h-full min-h-0 flex-col border-l border-zinc-800 bg-zinc-950">
              <div className="border-b border-zinc-800 px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
                {uiText.rightPanelTitle}
              </div>
              <ResizableSplit
                orientation="horizontal"
                storageKey="jb.split.diag-props"
                initialRatio={0.65}
                minRatio={0.35}
                maxRatio={0.85}
                className="min-h-0 flex-1"
                first={
                  <DiagnosticsPanel
                    workspaceState={panelState}
                    onReveal={(line, column) => {
                      setRevealPosition({ line, column });
                      if (editorCollapsed && !compare) {
                        setEditorCollapsed(false);
                      }
                    }}
                    onApplyLogicFix={(issue) => {
                      void handleApplyLogicFix(issue);
                    }}
                    onRepairWithLlm={(issues) => {
                      void handleRepairWithLlm(issues);
                    }}
                    applyBusyIssueId={applyBusyIssueId}
                    repairBusy={repairBusy}
                  />
                }
                second={
                  <PropertiesInspector
                    scratch={activeScratch}
                    selectedBlockId={selectedBlockId}
                  />
                }
              />
            </aside>
          }
        />
      </div>

      <StatusBar connection={connection} dirty={dirty} fileName={document.fileName} />
      <CompareResultsToast state={compareToast} onClose={() => setCompareToast(null)} />

      <AuthDialog
        open={authDialogOpen}
        busy={auth.busy}
        error={auth.error}
        onClose={() => {
          setAuthDialogOpen(false);
          auth.setError(null);
        }}
        onLogin={async (email, password) => {
          await auth.login(email, password);
        }}
        onRegister={async (input) => {
          const result = await auth.register(input);
          return result.message || uiText.authRegisterOk;
        }}
      />

      {auth.user ? (
        <CabinetDialog
          key={`${auth.user.id}:${auth.user.role}`}
          open={cabinetOpen}
          user={auth.user}
          busy={auth.busy}
          error={auth.error}
          onClose={() => {
            setCabinetOpen(false);
            auth.setError(null);
          }}
          onLogout={async () => {
            await auth.logout();
          }}
          onChangePassword={async (currentPassword, newPassword) => {
            await auth.changePassword(currentPassword, newPassword);
          }}
          onUpdateRole={async (role) => {
            await auth.updateRole(role);
          }}
        />
      ) : null}

      <span className="sr-only">{uiText.appName}</span>
    </div>
  );
}

function toErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiClientError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return fallback;
}
