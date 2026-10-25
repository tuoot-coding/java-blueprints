"""Тексты статической диагностики. В сообщения не подставляется исходный код."""

from __future__ import annotations

from enum import StrEnum


class AnalysisRule(StrEnum):
    UNREACHABLE = "java.unreachable_statement"
    EMPTY_METHOD = "java.empty_method_body"
    EMPTY_CONTROL = "java.empty_control_body"
    EMPTY_IF_ELSE = "java.empty_if_then_with_else"
    INFINITE_FOR = "java.for_infinite_without_break"
    COMPLEXITY = "java.cyclomatic_complexity"
    UNSUPPORTED = "java.unsupported_construct"
    DUPLICATE_IF = "java.duplicate_if_condition_text"
    LONG_METHOD = "java.long_method"
    DUPLICATE_LOGIC = "java.duplicate_logic"


QUICK_FIX_REMOVE_UNREACHABLE = "Удалить недостижимый оператор"

_EXPLANATIONS: dict[str, str] = {
    AnalysisRule.UNREACHABLE: (
        "Оператор стоит в том же блоке после return, throw, break или continue "
        "и структурно недостижим. Вложенные условия не считаются безусловным выходом."
    ),
    AnalysisRule.EMPTY_METHOD: "В теле метода нет операторов. Комментарии телом не считаются.",
    AnalysisRule.EMPTY_CONTROL: (
        "Ветвь или тело цикла не содержит операторов. Это структурная пустота, не оценка смысла."
    ),
    AnalysisRule.EMPTY_IF_ELSE: (
        "Пустая ветвь then при наличии else. Семантика условия не вычисляется."
    ),
    AnalysisRule.INFINITE_FOR: (
        "У classic for нет условия и в теле нет break. Если внутри есть непрозрачная "
        "конструкция, правило молчит: отсутствие break не доказано."
    ),
    AnalysisRule.COMPLEXITY: (
        "Оценка Маккейба: 1 плюс if, while, do, for, for-each, catch и операторы "
        "&& и || внутри условий. Непрозрачные узлы не раскрываются, оценка может быть занижена. "
        "Семантическое сравнение условий отложено."
    ),
    AnalysisRule.UNSUPPORTED: (
        "Конструкция сохранена срезом исходного текста. Редактор не выводит для нее поведение."
    ),
    AnalysisRule.DUPLICATE_IF: (
        "У соседних if в одном блоке совпал точный текст условия. "
        "Семантическое равенство выражений на этом этапе отложено."
    ),
    AnalysisRule.LONG_METHOD: (
        "Метод превышает порог по числу строк или операторов. "
        "Рекомендуется декомпозиция на более мелкие методы с сохранением смысла."
    ),
    AnalysisRule.DUPLICATE_LOGIC: (
        "Два метода имеют совпадающую или очень похожую логику тела. "
        "Имеет смысл вынести общий фрагмент в один хелпер."
    ),
}


def analysis_explanation(rule: AnalysisRule) -> str:
    return _EXPLANATIONS[rule]


def unreachable_message() -> str:
    return "Оператор недостижим: раньше в этом блоке есть безусловный выход."


def empty_method_message(name: str) -> str:
    return f"Тело метода {name} не содержит операторов."


def empty_control_message() -> str:
    return "Тело ветви или цикла пустое."


def empty_if_else_message() -> str:
    return "Ветвь then пустая, при этом есть ветвь else."


def infinite_for_message() -> str:
    return "Цикл for(;;) не содержит break. Выход из него этой структурой не показан."


def complexity_message(name: str, value: int) -> str:
    return f"Цикломатическая сложность метода {name} равна {value}."


def unsupported_message(reason: str) -> str:
    return f"Конструкция {reason} сохранена как текст и не разбирается структурно."


def duplicate_if_message() -> str:
    return "Соседние if имеют одинаковый текст условия."


def long_method_message(name: str, lines: int, statements: int) -> str:
    return (
        f"Метод {name} перегружен: ~{lines} строк, ~{statements} операторов. "
        "Рекомендуется декомпозиция."
    )


def duplicate_logic_message(left: str, right: str, *, exact: bool) -> str:
    kind = "точное" if exact else "близкое"
    return f"Обнаружено {kind} дублирование логики методов {left} и {right}."
