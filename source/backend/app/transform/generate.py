"""Структурная генерация Java.

Основной путь правок - патч исходника. Этот модуль не собирает файл заново из
подписей узлов: такая сборка потеряла бы пробелы и незнакомые токены.

Если IR содержит unsupported или разбор нашел синтаксическую ошибку, генерация
отклоняется кодом GENERATION_REFUSED. Если дерево полностью поддержано и
синтаксис разобран, возвращается исходный текст без изменений: это единственная
байт-в-байт реконструкция без семантических правок.
"""

from __future__ import annotations

import re
from http import HTTPStatus

from app.core.errors import ApplicationError
from app.ir.builder import build_structural_ir
from app.ir.models import IrNodeKind
from app.ir.query import walk_ir
from app.parser.service import inspect_java_source
from app.schemas.errors import ErrorCode
from app.transform.fingerprint import source_fingerprint

_MAX_REASONS = 12
_REASON = re.compile(r"^[A-Za-z0-9_]{1,80}$")


def generate_java_from_ir(source: str) -> tuple[str, str]:
    """Возвращает (source, source_hash) либо отклоняет генерацию."""
    inspection = inspect_java_source(source)
    ir = build_structural_ir(source, inspection.tree)
    unsupported = [node for node in walk_ir(ir) if node.kind == IrNodeKind.UNSUPPORTED]
    reasons = sorted(
        {
            reason
            for node in unsupported
            for reason in [node.reason or node.syntax_type]
            if reason and _REASON.fullmatch(reason)
        }
    )
    if inspection.result.has_syntax_errors or unsupported:
        raise ApplicationError(
            ErrorCode.GENERATION_REFUSED,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            details={
                "has_syntax_errors": inspection.result.has_syntax_errors,
                "unsupported_count": len(unsupported),
                "reasons": reasons[:_MAX_REASONS],
            },
        )
    return source, source_fingerprint(source)
