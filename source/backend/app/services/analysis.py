"""Оркестрация статического анализа."""

from __future__ import annotations

from app.analysis.engine import AnalysisRun, run_static_analysis
from app.graph.builder import build_method_cfg
from app.graph.models import CfgGraph
from app.ir.query import list_methods
from app.services.inspection import LoadedJava, load_java


def analyze_source_request(source: str, *, max_source_bytes: int) -> tuple[AnalysisRun, LoadedJava]:
    loaded = load_java(source, max_source_bytes=max_source_bytes)
    graphs: dict[str, CfgGraph] = {
        method.id: build_method_cfg(method) for method in list_methods(loaded.ir)
    }
    run = run_static_analysis(loaded.ir, graphs, source=loaded.source)
    return run, loaded
