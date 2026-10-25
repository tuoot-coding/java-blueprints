"""Сквозной сценарий: синтаксис -> Scratch-блок-схема -> анализ -> LLM."""

from __future__ import annotations

from dataclasses import dataclass, replace

from app.analysis.engine import AnalysisRun, run_static_analysis
from app.core.config import Settings
from app.core.logging import log_activity
from app.graph.builder import build_method_cfg
from app.graph.models import CfgGraph
from app.ir.query import list_methods
from app.llm.call_options import resolve_llm_options
from app.llm.flowchart_assist import FlowchartAssistResult, assist_flowchart
from app.llm.logical_review import LogicalReviewResult, review_java_logic
from app.llm.source_pack import build_llm_source_pack
from app.texts.analysis import AnalysisRule
from app.parser.models import JavaParseResult
from app.services.graph import _empty_graph, _with_limitation
from app.services.inspection import LoadedJava, load_java
from app.structure.blocks import build_structural_blocks
from app.structure.models import StructuralBlock
from app.structure.scratch import ScratchProgram, build_scratch_program


@dataclass(frozen=True, slots=True)
class WorkspaceInspectResult:
    loaded: LoadedJava
    parse: JavaParseResult
    blocks: tuple[StructuralBlock, ...]
    scratch: ScratchProgram
    graph: CfgGraph
    analysis: AnalysisRun
    logical_review: LogicalReviewResult | None
    flowchart_assist: FlowchartAssistResult | None
    llm_configured: bool


def inspect_workspace_request(source: str, settings: Settings) -> WorkspaceInspectResult:
    log_activity(
        "workspace_inspect_start", source_chars=len(source), include_llm=settings.llm_enabled
    )
    loaded = load_java(source, max_source_bytes=settings.max_java_source_bytes)
    parse = loaded.inspection.result
    log_activity(
        "workspace_parse_done",
        status=parse.status.value,
        syntax_errors=parse.has_syntax_errors,
        diagnostics=len(parse.diagnostics),
        source_hash=loaded.source_hash[:16],
    )

    blocks = build_structural_blocks(loaded.ir)
    scratch = build_scratch_program(loaded.ir)
    log_activity(
        "workspace_scratch_built",
        method=scratch.method_name,
        scratch_blocks=len(scratch.blocks),
        structure_blocks=len(blocks),
    )

    graph = _select_graph(loaded)
    graphs = {method.id: build_method_cfg(method) for method in list_methods(loaded.ir)}
    analysis = run_static_analysis(loaded.ir, graphs, source=loaded.source)
    log_activity(
        "workspace_static_analysis_done",
        static_diagnostics=len(analysis.diagnostics),
        quick_fixes=len(analysis.quick_fixes),
        unsupported=analysis.metrics.unsupported_count,
    )

    options = resolve_llm_options(settings)
    llm_configured = options is not None
    logical_review: LogicalReviewResult | None = None
    flowchart_assist: FlowchartAssistResult | None = None
    log_activity("workspace_llm_config", configured=llm_configured, enabled=settings.llm_enabled)

    if options is not None and not parse.has_syntax_errors:
        source_pack = build_llm_source_pack(loaded.source, loaded.ir)
        bloat_notes = _bloat_summary(analysis)
        summary = _syntax_summary(parse, scratch, graph, source_pack) + bloat_notes
        call_options = options
        if source_pack.truncated:
            call_options = replace(
                options,
                timeout_seconds=min(
                    300.0, max(options.timeout_seconds, options.timeout_seconds * 1.5)
                ),
            )
        log_activity(
            "workspace_llm_pack",
            mode=source_pack.mode,
            truncated=source_pack.truncated,
            pack_chars=source_pack.payload_chars,
            control_nodes=source_pack.control_nodes,
            methods=",".join(source_pack.included_methods[:20]),
        )
        logical_review = review_java_logic(
            source=loaded.source,
            source_pack=source_pack,
            syntax_summary=summary,
            options=call_options,
        )
        if settings.llm_include_flowchart_assist:
            flowchart_assist = assist_flowchart(
                source_pack=source_pack,
                method_name=scratch.method_name,
                options=call_options,
                enabled=True,
            )
    elif options is not None and parse.has_syntax_errors:
        logical_review = LogicalReviewResult(
            status="skipped_syntax_errors",
            issues=(),
            notes=("Логический LLM-анализ пропущен: в исходнике есть синтаксические ошибки.",),
            model=settings.llm_model,
            error_reason="syntax_errors",
        )
        log_activity("workspace_llm_skipped_syntax_errors")

    issue_count = len(logical_review.issues) if logical_review else 0
    log_activity(
        "workspace_inspect_done",
        llm_issues=issue_count,
        scratch_blocks=len(scratch.blocks),
    )
    return WorkspaceInspectResult(
        loaded=loaded,
        parse=parse,
        blocks=blocks,
        scratch=scratch,
        graph=graph,
        analysis=analysis,
        logical_review=logical_review,
        flowchart_assist=flowchart_assist,
        llm_configured=llm_configured,
    )


def _select_graph(loaded: LoadedJava) -> CfgGraph:
    methods = list_methods(loaded.ir)
    if not methods:
        return _empty_graph("no_method")
    graph = build_method_cfg(methods[0])
    if len(methods) > 1:
        graph = _with_limitation(graph, "selected_first_method", None)
    return graph


def _syntax_summary(
    parse: JavaParseResult,
    scratch: ScratchProgram,
    graph: CfgGraph,
    source_pack: object,
) -> str:
    from app.llm.source_pack import LlmSourcePack

    pack_bits = ""
    if isinstance(source_pack, LlmSourcePack):
        pack_bits = (
            f"; pack={source_pack.mode}; control_nodes={source_pack.control_nodes}; "
            f"outline_chars={len(source_pack.logic_outline)}"
        )
    parts = [
        f"parse={parse.status.value}",
        f"syntax_err={parse.has_syntax_errors}",
        f"diag={len(parse.diagnostics)}",
        f"scratch={scratch.method_name or '-'}/{len(scratch.blocks)}",
        f"cfg={len(graph.nodes)}/partial={graph.partial}",
    ]
    return "; ".join(parts) + pack_bits


def _bloat_summary(analysis: AnalysisRun) -> str:
    long_count = sum(
        1 for item in analysis.diagnostics if item.rule_id == AnalysisRule.LONG_METHOD
    )
    dup_count = sum(
        1 for item in analysis.diagnostics if item.rule_id == AnalysisRule.DUPLICATE_LOGIC
    )
    if long_count == 0 and dup_count == 0:
        return ""
    return f"; static_bloat long_methods={long_count} duplicate_logic={dup_count}"
