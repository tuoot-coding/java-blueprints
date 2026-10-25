"""Опциональное текстовое описание блок-схемы от GigaChat. Scratch строится из IR."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.core.logging import log_activity
from app.llm.call_options import LlmCallOptions
from app.llm.client import LlmClientError, chat_completion
from app.llm.json_extract import parse_json_object
from app.llm.prompts import build_flowchart_messages, flowchart_chat_payload
from app.llm.source_pack import LlmSourcePack

logger = logging.getLogger("app.llm")


@dataclass(frozen=True, slots=True)
class FlowchartAssistNode:
    id: str
    kind: str
    label: str


@dataclass(frozen=True, slots=True)
class FlowchartAssistEdge:
    source_id: str
    target_id: str
    label: str | None


@dataclass(frozen=True, slots=True)
class FlowchartAssistResult:
    status: str
    method_name: str | None
    summary: str | None
    nodes: tuple[FlowchartAssistNode, ...]
    edges: tuple[FlowchartAssistEdge, ...]
    limitations: tuple[str, ...]
    model: str | None
    error_reason: str | None = None


def assist_flowchart(
    *,
    source_pack: LlmSourcePack | None = None,
    method_name: str | None = None,
    options: LlmCallOptions | None = None,
    enabled: bool = False,
    **_kwargs: object,
) -> FlowchartAssistResult:
    """При enabled=false возвращает disabled; иначе запрашивает краткое описание у GigaChat."""
    if not enabled or options is None or source_pack is None:
        return FlowchartAssistResult(
            status="disabled",
            method_name=method_name,
            summary=None,
            nodes=(),
            edges=(),
            limitations=("Scratch-блок-схема строится из структурного IR, не из LLM.",),
            model=None if options is None else options.model,
            error_reason="disabled",
        )

    messages = build_flowchart_messages(
        source_payload=source_pack.payload_text,
        method_name=method_name,
    )
    payload = flowchart_chat_payload(
        model=options.model,
        messages=messages,
        provider=options.credentials.provider,
    )
    log_activity("llm_flowchart_assist_start", model=options.model, method=method_name)
    try:
        content = chat_completion(
            credentials=options.credentials,
            base_url=options.base_url,
            oauth_url=options.oauth_url,
            payload=payload,
            timeout_seconds=min(60.0, options.timeout_seconds),
            verify_ssl=options.verify_ssl,
        )
        data = parse_json_object(content)
        nodes = tuple(_parse_node(item) for item in data.get("nodes", []) if isinstance(item, dict))
        edges = tuple(_parse_edge(item) for item in data.get("edges", []) if isinstance(item, dict))
        limitations_raw = data.get("limitations", [])
        limitations = (
            tuple(str(item) for item in limitations_raw) if isinstance(limitations_raw, list) else ()
        )
        summary = data.get("summary")
        name = data.get("method_name")
        log_activity("llm_flowchart_assist_ok", nodes=len(nodes), edges=len(edges))
        return FlowchartAssistResult(
            status="ok",
            method_name=str(name) if isinstance(name, str) else method_name,
            summary=str(summary) if isinstance(summary, str) else None,
            nodes=nodes,
            edges=edges,
            limitations=limitations,
            model=options.model,
        )
    except LlmClientError as exc:
        log_activity("llm_flowchart_assist_unavailable", reason=exc.reason)
        return FlowchartAssistResult(
            status="unavailable",
            method_name=method_name,
            summary=None,
            nodes=(),
            edges=(),
            limitations=(),
            model=options.model,
            error_reason=exc.reason,
        )
    except (ValueError, TypeError, KeyError) as exc:
        logger.warning("llm_flowchart_assist_invalid error=%s", type(exc).__name__)
        return FlowchartAssistResult(
            status="invalid_response",
            method_name=method_name,
            summary=None,
            nodes=(),
            edges=(),
            limitations=(),
            model=options.model,
            error_reason="invalid_response",
        )


def _parse_node(item: dict[str, Any]) -> FlowchartAssistNode:
    return FlowchartAssistNode(
        id=str(item.get("id", "")),
        kind=str(item.get("kind", "unknown")),
        label=str(item.get("label", "")),
    )


def _parse_edge(item: dict[str, Any]) -> FlowchartAssistEdge:
    label = item.get("label")
    return FlowchartAssistEdge(
        source_id=str(item.get("source_id", "")),
        target_id=str(item.get("target_id", "")),
        label=str(label) if isinstance(label, str) else None,
    )
