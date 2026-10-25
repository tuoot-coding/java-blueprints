"""Шаблоны запросов к LLM. Исходник и контур - только в user-сообщении."""

from __future__ import annotations

from typing import Any

LOGICAL_REVIEW_SYSTEM = """Ты senior Java reviewer для Java Blueprints (DeepSeek).
Вход: LOGIC_OUTLINE + код (может быть усечен). Это не javac.

СТРОГИЙ ФОРМАТ: верни РОВНО один JSON-объект, без markdown, без текста до/после.
Схема:
{
  "issues": [
    {
      "id": "string",
      "severity": "error"|"warning"|"structure",
      "affects_execution": true|false,
      "code": "llm.logic.*|llm.complexity.*|llm.structure.*|llm.bloat.*",
      "title": "string",
      "message": "string",
      "explanation": "string",
      "start_line": 1,
      "start_column": 1,
      "end_line": 1,
      "end_column": 1,
      "confidence": "high"|"medium",
      "fix": null
    }
  ],
  "notes": ["string"]
}
fix: null ИЛИ объект
{title, replacement, start_line, start_column, end_line, end_column,
 start_byte, end_byte, expected_snippet, auto_applicable}.
Все числовые поля - целые. confidence только "high" или "medium".

ТРИ КОРЗИНЫ severity (обязательно ровно одна на issue):

1) severity="error", affects_execution=true, code llm.logic.* или llm.complexity.*
   Серьёзные проблемы, которые реально ломают результат, падают, зависают,
   портят контракт, или критичная алгоритмическая сложность (Big O неадекватна
   задаче: квадрат/куб там, где нужен линейный проход по большим данным).
   Примеры: неверный if/return/throw, == для объектов, гарантированный NPE,
   бесконечный цикл, код после return, сломанный switch, O(n^2)/O(n^3) вместо
   допустимого O(n) на больших входах.

2) severity="warning", affects_execution=true, code llm.logic.*
   Некритичные или ситуативные риски: слабые проверки, возможный NPE только
   на редком входе, хрупкая ветка, сомнительный порядок операций без доказанного
   падения на типичных данных. Не завышай до error.

3) severity="structure", affects_execution=false,
   code llm.structure.*|llm.bloat.*|llm.complexity.* (только оценка без бага)
   НЕ влияет на результат при тех же входах: читаемость, длинный метод,
   дублирование кода, лишняя вложенность, монолит, «метод превышает порог
   строк/операторов». Это структурные замечания, не логические ошибки.

АНТИ-ГАЛЛЮЦИНАЦИИ (обязательно):
- Не выдумывай баги «на всякий случай». Нет прямого доказательства в коде - не пиши issue.
- Если серьёзных error нет - issues для error должны быть ПУСТЫМИ (не добавляй фиктивные).
- Если неуверен - либо warning с evidence в explanation, либо вообще не включай.
- Не заполняй issues ради «полноты списка». Допустимо и желательно: "issues": [].
- Не стиль и не именование. Не выдумывай API и несуществующие методы.
- Не меть structure как error/warning и наоборот.
- Big O без логического бага, но критичная для задачи - error + llm.complexity.*.
- fix только для безопасного локального патча при реальной ошибке.
"""

TEST_SCRIPTS_SYSTEM = """Ты генерируешь console-сценарии для проверки РАБОТЫ Java-кода.
Среда: javac + java MainClass, stdin/stdout. НЕ JUnit, НЕ assert, НЕ файлы/сеть.
Метрики wall/cpu/rss измеряет раннер - НЕ выдумывай числа в JSON.

На вход даны SOURCE и KNOWN_ISSUES (результаты ревью исходника; может быть []).
Сценарии строятся ПОСЛЕ ревью. Затем их ЗАПУСТЯТ на исходнике: ресурсы
original станут baseline для сравнения с отредактированным кодом.

Верни РОВНО один JSON-объект, без markdown, без текста до/после:
{
  "tests": [
    {
      "id": "t01",
      "name": "short_name",
      "description": "что проверяет сценарий (1-2 предложения)",
      "error_description": "подробно про ошибку/риск или пустая строка",
      "purpose": "workability"|"exploit_error",
      "related_issue_id": null,
      "expects_original_failure": false,
      "stdin": "",
      "expected_stdout": "",
      "expected_exit_code": 0,
      "main_class_hint": "Main"
    }
  ],
  "notes": []
}

Жёсткие правила:
1) Ровно 10 tests, id t01..t10. Каждый - сквозной прогон main на stdin.
2) ГЛАВНОЕ: workability ОБЯЗАНЫ завершаться на SOURCE (exit 0, без Exception
   и без ожидания лишнего ввода). Дай ВСЕ значения, которые Scanner/read
   читает в main, иначе программа зависнет. Мысленно прогони ДО записи в JSON.
3) main_class_hint = класс с public static void main из SOURCE (иначе
   публичный класс; если неясно - "Main").
4) stdin - только то, что SOURCE реально читает (Scanner/BufferedReader).
   Формат и число значений - строго как в коде. Не придумывай меню/файлы/HTTP.
5) description - понятное описание проверки. error_description:
   - для workability: "" или краткий риск, если граничный ввод;
   - для exploit_error: ПОДРОБНО какая ошибка из KNOWN_ISSUES, как stdin
     её провоцирует, какой провал ожидается у исходника (NPE/неверный
     ответ/зависание и т.п.).
6) purpose="workability" (большинство): expected_stdout/exit - факт SOURCE.
7) Если в KNOWN_ISSUES есть severity="error": минимум 1 exploit_error
   (expects_original_failure=true, related_issue_id=id). Stdin целенаправленно
   ломает исходник. Без error - НЕ делай фиктивный exploit.
8) Не галлюцинируй баги и входы. Короткие строки (<=200). Только JSON.
"""

REPAIR_SYSTEM = """Ты senior Java engineer для Java Blueprints (DeepSeek).
Цель: исправить ТОЛЬКО указанные issues, без регрессий; при необходимости
оптимизировать и декомпозировать монолит.

Верни ТОЛЬКО JSON:
{
  "java": string|null,
  "replacements": [{"start_line":int,"end_line":int,"replacement":string}],
  "fixed_issue_ids": [string],
  "notes": [string],
  "self_tests": [{"name":string,"status":"pass"|"fail","detail":string}]
}

Формат ответа:
- Малый/полный SOURCE_FULL*: "java" = полный compilation unit, "replacements"=[].
- Крупный/усечённый: "replacements" по затронутым методам, "java"=null.
- Не вырезай и не переписывай нетронутые методы "для красоты".

Жёсткие правила (без регрессий):
1) Исправь issues из списка. Не трогай код вне их области, если это не нужно для фикса.
2) Не вводи новые логические ошибки: == для String/объектов, NPE-порядок,
   бесконечные циклы, код после return/throw, сломанные ветки if/else/switch,
   изменение контракта публичных методов, порчу I/O.
3) Сохрани публичный API (имена/сигнатуры public/protected), package, imports по смыслу.
4) Синтаксис Java должен быть валиден.
5) Оптимизация/декомпозиция - только если issues это требуют (long_method, duplicate,
   complexity) или правка неизбежно упрощает код. Новые helpers - private в том же классе.
6) Без сторонних зависимостей. Без markdown вне JSON.

ОБЯЗАТЕЛЬНЫЕ SELF-TESTS перед отправкой (мысленно прогони и заполни self_tests):
- syntax_ok: код компилируется синтаксически.
- issues_fixed: каждый id из ISSUES реально устранён или честно не в fixed_issue_ids.
- no_new_logic_bugs: не появились == для объектов, NPE, мёртвый код после return,
  сломанный switch/if, бесконечный цикл.
- api_preserved: публичные сигнатуры и поведение I/O сохранены.
- helpers_private: новые методы - private (если добавлялись).
Если любой self_test = fail - ИСПРАВЬ код и повтори проверки, пока все pass.
В ответ пользователю отправляй только вариант, где все self_tests = pass.
"""

SCHEME_TO_CODE_SYSTEM = """Ты генерируешь Java по модульной логической блок-схеме
для Java Blueprints (DeepSeek).

Верни ТОЛЬКО JSON:
{"java": string, "modules_written": [string], "notes": [string]}

ТЗ:
1) MODULAR_SCHEME - текстовый контур той же модели, из которой UI строит блок-схему
   (модули class/method, блоки, next/body/else, snippet).
2) Реализуй рекурсивно по next (порядок) и body/else/children (вложенность).
3) Код ОБЯЗАН соответствовать схеме: порядок операторов = next, вложенность = body.
   SOURCE - эталон API/импортов; при конфликте схема важнее старого тела метода.
4) Блоки user_* - вставь source_snippet/label в цепочку.
5) Полный валидный Java compilation unit. Не выдумывай удалённые блоки.
6) Helpers - private. Сохрани package и public API, если они есть в SOURCE.
"""

FLOWCHART_SYSTEM = """Опиши модульную логическую блок-схему Java по LOGIC_OUTLINE (ISO 5807).
Узлы: start/end, process, decision, loop, predefined, data, module.
Не выдумывай узлов вне контура. Ответ ТОЛЬКО JSON по схеме.
"""

_REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "severity": {"type": "string"},
                    "affects_execution": {"type": "boolean"},
                    "code": {"type": "string"},
                    "title": {"type": "string"},
                    "message": {"type": "string"},
                    "explanation": {"type": "string"},
                    "start_line": {"type": "integer"},
                    "start_column": {"type": "integer"},
                    "end_line": {"type": "integer"},
                    "end_column": {"type": "integer"},
                    "confidence": {"type": "number"},
                    "fix": {"type": ["object", "null"]},
                },
                "required": [
                    "id",
                    "severity",
                    "affects_execution",
                    "code",
                    "title",
                    "message",
                ],
            },
        },
        "notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["issues", "notes"],
    "additionalProperties": True,
}

_TEST_SCRIPTS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "tests": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "error_description": {"type": "string"},
                    "purpose": {"type": "string"},
                    "related_issue_id": {"type": ["string", "null"]},
                    "expects_original_failure": {"type": "boolean"},
                    "stdin": {"type": "string"},
                    "expected_stdout": {"type": "string"},
                    "expected_exit_code": {"type": "integer"},
                    "main_class_hint": {"type": ["string", "null"]},
                },
                "required": [
                    "id",
                    "name",
                    "stdin",
                    "expected_stdout",
                    "expected_exit_code",
                ],
            },
        },
        "notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["tests", "notes"],
    "additionalProperties": True,
}

_REPAIR_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "java": {"type": ["string", "null"]},
        "replacements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start_line": {"type": "integer"},
                    "end_line": {"type": "integer"},
                    "replacement": {"type": "string"},
                },
                "required": ["start_line", "end_line", "replacement"],
            },
        },
        "fixed_issue_ids": {"type": "array", "items": {"type": "string"}},
        "notes": {"type": "array", "items": {"type": "string"}},
        "self_tests": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "status": {"type": "string"},
                    "detail": {"type": "string"},
                },
                "required": ["name", "status"],
            },
        },
    },
    "required": ["fixed_issue_ids", "notes", "self_tests"],
    "additionalProperties": True,
}

_SCHEME_TO_CODE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "java": {"type": "string"},
        "modules_written": {"type": "array", "items": {"type": "string"}},
        "notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["java", "modules_written", "notes"],
    "additionalProperties": True,
}

_FLOWCHART_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "method_name": {"type": "string"},
        "summary": {"type": "string"},
        "nodes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "kind": {"type": "string"},
                    "label": {"type": "string"},
                },
                "required": ["id", "kind", "label"],
            },
        },
        "edges": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source_id": {"type": "string"},
                    "target_id": {"type": "string"},
                    "label": {"type": "string"},
                },
                "required": ["source_id", "target_id"],
            },
        },
        "limitations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "nodes", "edges", "limitations"],
    "additionalProperties": True,
}


def build_logical_review_messages(
    *,
    source_payload: str,
    syntax_summary: str,
    pack_mode: str,
    truncated: bool,
) -> list[dict[str, str]]:
    trunc = (
        "Пакет усечен: опирайся только на присланный outline+code; не выдумывай остальное."
        if truncated
        else "Пакет полный."
    )
    user = (
        f"Проверь Java: логика, монолит, Big O, дубли. Перечисли все issues. "
        f"mode={pack_mode}. {trunc}\n"
        f"meta: {syntax_summary}\n\n"
        f"{source_payload}"
    )
    return [
        {"role": "system", "content": LOGICAL_REVIEW_SYSTEM},
        {"role": "user", "content": user},
    ]


REVIEW_VERIFY_SYSTEM = """Ты проверяешь список issues от предыдущего Java-review.
Задача: отсеять ЛОЖНЫЕ срабатывания. Не добавляй новых issues.

Верни РОВНО один JSON-объект:
{"keep_ids":["id",...],"drop_ids":["id",...],"notes":["string"]}

Правила drop (ложная ошибка):
- В explanation/message прямо сказано, что это НЕ ошибка / не баг /
  допустимо / ложное срабатывание / false positive / «не является ошибкой».
- Нет доказательств бага в коде; issue галлюцинация или стиль.
- severity=structure без реального дефекта исполнения - можно оставить
  в keep, если замечание структурное честное.

keep_ids - реальные проблемы. drop_ids - не показывать пользователю.
Каждый входной id ровно в одном из списков. Только JSON.
"""


def build_review_verify_messages(
    *,
    source_payload: str,
    issues_payload: str,
) -> list[dict[str, str]]:
    user = (
        "Повторный анализ issues. Убери ложные (если пояснение говорит, "
        "что это не ошибка, или нет доказательства бага).\n\n"
        f"ISSUES:\n{issues_payload}\n\nSOURCE_CONTEXT:\n{source_payload[:24000]}"
    )
    return [
        {"role": "system", "content": REVIEW_VERIFY_SYSTEM},
        {"role": "user", "content": user},
    ]


def build_repair_messages(
    *,
    source_payload: str,
    issues_payload: str,
    pack_mode: str,
    truncated: bool,
    static_summary: str = "",
    prefer_replacements: bool = False,
) -> list[dict[str, str]]:
    if prefer_replacements or truncated:
        format_hint = (
            "Крупный файл: верни replacements по затронутым методам "
            "(start_line/end_line inclusive, replacement = полный новый "
            "текст фрагмента). java=null."
        )
    else:
        format_hint = "Верни полный файл в java; replacements=[]."
    trunc = (
        "Пакет усечен: исправляй видимые hotspots; нетронутое не вырезай."
        if truncated
        else "Дан полный исходник."
    )
    static_line = f"\nSTATIC: {static_summary}" if static_summary else ""
    user = (
        f"Исправь issues БЕЗ регрессий. При необходимости оптимизируй/декомпозируй. "
        f"Прогони SELF-TESTS и верни только вариант со всеми pass. "
        f"mode={pack_mode}. {trunc} {format_hint}{static_line}\n"
        f"ISSUES:\n{issues_payload}\n\n"
        f"{source_payload}"
    )
    return [
        {"role": "system", "content": REPAIR_SYSTEM},
        {"role": "user", "content": user},
    ]


def build_scheme_to_code_messages(
    *,
    scheme_outline: str,
    source: str,
    module_focus: str | None = None,
) -> list[dict[str, str]]:
    focus = (
        f"Сейчас реализуй модуль: {module_focus}.\n"
        if module_focus
        else "Реализуй все модули рекурсивно строго по MODULAR_SCHEME.\n"
    )
    user = (
        f"{focus}"
        f"Ниже контур схемы (тот же вид, из которого строится блок-схема UI).\n"
        f"MODULAR_SCHEME:\n{scheme_outline}\n\nSOURCE:\n{source}"
    )
    return [
        {"role": "system", "content": SCHEME_TO_CODE_SYSTEM},
        {"role": "user", "content": user},
    ]


def build_test_scripts_messages(
    *,
    source: str,
    known_issues: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    issues_text = format_issues_for_test_scripts(known_issues or [])
    serious = sum(
        1
        for item in (known_issues or [])
        if str(item.get("severity", "")).lower() == "error"
    )
    exploit_hint = (
        f"В KNOWN_ISSUES есть {serious} severity=error: "
        "обязателен минимум 1 purpose=exploit_error."
        if serious
        else "Серьёзных error нет: только purpose=workability, без фиктивных exploit."
    )
    user = (
        "Сгенерируй ровно 10 console-тестов (stdin -> stdout, java main) "
        "ПОСЛЕ ревью. Workability ОБЯЗАНЫ реально отрабатывать на SOURCE "
        "(без краша). У каждого теста заполняй description и "
        "error_description (для exploit - подробно). "
        f"{exploit_hint} "
        "Ответ - только JSON по схеме. Без markdown и без JUnit.\n\n"
        f"KNOWN_ISSUES:\n{issues_text}\n\nSOURCE:\n{source}"
    )
    return [
        {"role": "system", "content": TEST_SCRIPTS_SYSTEM},
        {"role": "user", "content": user},
    ]


def format_issues_for_test_scripts(issues: list[dict[str, Any]]) -> str:
    """Краткий список issues ревью для генерации тестов (после logical review)."""
    if not issues:
        return "(no issues)"
    lines: list[str] = []
    for item in issues:
        issue_id = str(item.get("id", "?"))
        severity = str(item.get("severity", "warning"))
        code = str(item.get("code", "?"))
        title = str(item.get("title", ""))
        message = str(item.get("message", ""))
        explanation = str(item.get("explanation", ""))[:240]
        start_line = item.get("start_line", "?")
        end_line = item.get("end_line", start_line)
        lines.append(
            f"- {issue_id}|{severity}|{code}|L{start_line}-{end_line}|{title}: "
            f"{message}"
            + (f" | {explanation}" if explanation else "")
        )
    return "\n".join(lines)


def build_flowchart_messages(
    *,
    source_payload: str,
    method_name: str | None,
) -> list[dict[str, str]]:
    name = method_name or "?"
    user = f"Опиши модульную блок-схему (фокус метод {name}).\n\n{source_payload}"
    return [
        {"role": "system", "content": FLOWCHART_SYSTEM},
        {"role": "user", "content": user},
    ]


def format_issues_for_repair(issues: list[dict[str, Any]]) -> str:
    """Компактный список ошибок для repair-запроса."""
    lines: list[str] = []
    for item in issues:
        issue_id = str(item.get("id", "?"))
        code = str(item.get("code", "?"))
        severity = str(item.get("severity", "warning"))
        title = str(item.get("title", ""))
        message = str(item.get("message", ""))
        start_line = item.get("start_line", "?")
        end_line = item.get("end_line", start_line)
        lines.append(f"- {issue_id}|{severity}|{code}|L{start_line}-{end_line}|{title}: {message}")
    return "\n".join(lines) if lines else "(no issues)"


def llm_chat_payload(
    *,
    model: str,
    messages: list[dict[str, str]],
    schema: dict[str, Any],
    temperature: float = 0.1,
    max_tokens: int = 2500,
    provider: str = "deepseek",
) -> dict[str, Any]:
    """DeepSeek/OpenAI: json_object. GigaChat legacy: json_schema."""
    if provider == "gigachat":
        return {
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": messages,
            "response_format": {
                "type": "json_schema",
                "schema": schema,
                "strict": True,
            },
        }
    return {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": messages,
        "response_format": {"type": "json_object"},
    }


def gigachat_chat_payload(
    *,
    model: str,
    messages: list[dict[str, str]],
    schema: dict[str, Any],
    temperature: float = 0.1,
    max_tokens: int = 2500,
) -> dict[str, Any]:
    """Совместимость: делегирует в llm_chat_payload (gigachat)."""
    return llm_chat_payload(
        model=model,
        messages=messages,
        schema=schema,
        temperature=temperature,
        max_tokens=max_tokens,
        provider="gigachat",
    )


def review_chat_payload(
    *,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int = 8192,
    provider: str = "deepseek",
) -> dict[str, Any]:
    return llm_chat_payload(
        model=model,
        messages=messages,
        schema=_REVIEW_SCHEMA,
        max_tokens=max_tokens,
        provider=provider,
    )


def repair_chat_payload(
    *,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int = 8192,
    provider: str = "deepseek",
) -> dict[str, Any]:
    return llm_chat_payload(
        model=model,
        messages=messages,
        schema=_REPAIR_SCHEMA,
        temperature=0.05,
        max_tokens=max_tokens,
        provider=provider,
    )


def scheme_to_code_chat_payload(
    *,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int = 8192,
    provider: str = "deepseek",
) -> dict[str, Any]:
    return llm_chat_payload(
        model=model,
        messages=messages,
        schema=_SCHEME_TO_CODE_SCHEMA,
        temperature=0.05,
        max_tokens=max_tokens,
        provider=provider,
    )


def test_scripts_chat_payload(
    *,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int = 4096,
    provider: str = "deepseek",
) -> dict[str, Any]:
    return llm_chat_payload(
        model=model,
        messages=messages,
        schema=_TEST_SCRIPTS_SCHEMA,
        temperature=0.0,
        max_tokens=max_tokens,
        provider=provider,
    )


def flowchart_chat_payload(
    *,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int = 2000,
    provider: str = "deepseek",
) -> dict[str, Any]:
    return llm_chat_payload(
        model=model,
        messages=messages,
        schema=_FLOWCHART_SCHEMA,
        max_tokens=max_tokens,
        provider=provider,
    )


def openrouter_chat_payload(
    *,
    model: str,
    messages: list[dict[str, str]],
    temperature: float = 0.1,
    max_tokens: int = 2500,
) -> dict[str, Any]:
    del temperature
    return review_chat_payload(model=model, messages=messages, max_tokens=max_tokens)
