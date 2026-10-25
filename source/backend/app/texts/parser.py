"""Пользовательские сообщения Parser."""

from __future__ import annotations

from types import MappingProxyType

from app.parser.models import DiagnosticCode

PARSER_MESSAGES: MappingProxyType[DiagnosticCode, str] = MappingProxyType(
    {
        DiagnosticCode.SYNTAX_ERROR: "Синтаксическая ошибка в исходном тексте Java.",
        DiagnosticCode.MISSING_NODE: (
            "В исходном тексте отсутствует ожидаемый синтаксический элемент."
        ),
    }
)


def get_parser_message(code: DiagnosticCode) -> str:
    return PARSER_MESSAGES[code]
