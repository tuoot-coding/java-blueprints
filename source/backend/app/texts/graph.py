"""Сообщения ограничений CFG. В текст не попадает исходный код пользователя."""

from __future__ import annotations

from types import MappingProxyType

GRAPH_ENTRY_LABEL = "вход"
GRAPH_EXIT_LABEL = "выход"
FOR_INFINITE_LABEL = "for (;;)"

_MESSAGES: MappingProxyType[str, str] = MappingProxyType(
    {
        "method_cfg_partial": (
            "CFG метода неполный: часть операторов не раскрыта во внутренние переходы."
        ),
        "opaque_statement": (
            "Оператор включен в CFG одним шагом с переходом дальше, без внутренних ребер."
        ),
        "labeled_jump": (
            "Помеченные break или continue не перенаправляются: цель метки не строится."
        ),
        "break_without_loop": "break вне смоделированного цикла не получил ребро.",
        "continue_without_loop": "continue вне смоделированного цикла не получил ребро.",
        "method_without_body": "У метода нет тела: CFG состоит из входа и выхода.",
        "no_method": "В исходнике нет метода, для которого можно построить CFG.",
        "selected_first_method": (
            "Имя метода не задано, построен CFG первого метода в порядке исходника."
        ),
        "ambiguous_method": (
            "Найдено несколько методов с одним именем, построен CFG первого совпадения."
        ),
        "incomplete_control": (
            "Управляющая конструкция неполная, внутренние ребра для нее не строятся."
        ),
    }
)


def graph_limitation_message(code: str, syntax_type: str | None = None) -> str:
    """Текст ограничения. syntax_type - имя узла грамматики, не фрагмент исходника."""
    if code == "opaque_statement" and syntax_type:
        return f"Оператор {syntax_type} включен в CFG одним шагом без внутренних ребер управления."
    if code == "method_cfg_partial" and syntax_type:
        return f"CFG неполный из-за конструкции {syntax_type}."
    return _MESSAGES.get(code, "CFG содержит структурное ограничение.")
