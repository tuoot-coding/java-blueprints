"""Подписи структурных блоков. Текст интерфейса не копируется в алгоритмы IR."""

from __future__ import annotations

from types import MappingProxyType

BLOCK_LABELS: MappingProxyType[str, str] = MappingProxyType(
    {
        "compilation_unit": "программа",
        "package_declaration": "пакет",
        "import_declaration": "импорт",
        "class_declaration": "класс",
        "field_declaration": "поле",
        "method_declaration": "метод",
        "constructor_declaration": "конструктор",
        "parameter": "параметр",
        "local_variable_declaration": "переменная",
        "block": "блок",
        "expression_statement": "выражение",
        "assignment_expression": "присваивание",
        "return_statement": "возврат",
        "break_statement": "break",
        "continue_statement": "continue",
        "throw_statement": "throw",
        "if_statement": "если",
        "while_statement": "while",
        "do_statement": "do-while",
        "for_statement": "for",
        "enhanced_for_statement": "for-each",
        "try_statement": "try",
        "catch_clause": "catch",
        "finally_clause": "finally",
        "method_invocation": "вызов",
        "object_creation_expression": "создание объекта",
        "binary_expression": "бинарное выражение",
        "unary_expression": "унарное выражение",
        "update_expression": "инкремент",
        "parenthesized_expression": "скобки",
        "literal": "литерал",
        "identifier": "имя",
        "comment": "комментарий",
        "unsupported": "неподдерживаемая конструкция",
    }
)


def structure_block_label(kind: str, name: str | None) -> str:
    """Короткая подпись блока. Длинный исходный текст в подпись не подставляется."""
    base = BLOCK_LABELS.get(kind, "узел")
    if name:
        return f"{base} {name}"
    return base
