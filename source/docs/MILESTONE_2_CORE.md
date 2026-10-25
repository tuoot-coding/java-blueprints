# Milestone 2 - IR, CFG, анализ, правки, SQLite

Дата: 2026-10-24. Корень: `C:\Users\stasechka\java-blueprints`.

`POST /api/v1/parser/parse` сохранен. Новые маршруты лежат под `/api/v1` и вызывают сервисы. Маршруты не обходят AST.

Координаты: `line_utf16_column_1_based_half_open`.

## Поддержано

- Структурный IR из tree-sitter-java: пакет, импорт, класс/интерфейс/enum/record, поле, метод, конструктор, параметр, блок, локальная переменная, if/while/do/for/for-each/try/try-with-resources/switch/return/break/continue/throw, вызов, `new`, field/array access, array creation, cast, ternary, instanceof, литерал, идентификатор, `this`/`super`, комментарий.
- Заголовок класса (`extends`, `implements`, параметры типа), модификаторы, тип и `throws` хранятся текстом, это не `unsupported`.
- Незнакомые конструкции (лямбда, method reference, анонимный класс) - лист `unsupported` с точным срезом исходника. См. `docs/JAVA_SUPPORT.md`.
- Структурные блоки: иерархия `body`/`else`/`condition`/`parameters`/`arguments`/`value`/`children` и `next` между операторами блока. `editable=false`.
- CFG метода: последовательность, if/else, while, classic for, return, throw (ребро `return` на выход), break/continue ближайшего while или classic for, вложенные блоки прозрачны.
- Анализ: недостижимый оператор после безусловного выхода в том же блоке, пустые тела, пустой then при else, `for(;;)` без break, сложность Маккейба, непрозрачные узлы, соседние if с тем же текстом условия.
- Quick fix удаляет весь недостижимый оператор. Применение сверяет sha256 UTF-8, диапазон и текст, затем снова парсит.
- Генерация: если есть синтаксическая ошибка или `unsupported`, ответ `generation_refused`. Иначе возвращается исходный текст без пересборки из подписей.
- SQLite: `projects` и `revisions`. Новая ревизия пишется только при совпадении `expected_revision`. `file_name` не открывается как путь.

## Ограничения CFG и анализа

- `do`, enhanced for, `try` / try-with-resources - один непрозрачный шаг с переходом дальше. Метод помечается `partial`. Внутренние break/return не извлекаются.
- `switch` моделируется в IR; CFG по case пока упрощён.
- Помеченные break/continue не получают ребро.
- Лямбда, method reference и анонимный класс не моделируются (`unsupported`).
- Методы интерфейса/enum/record входят в `list_methods`.
- Сложность не раскрывает непрозрачные узлы и может быть занижена. `&&` и `||` считаются только внутри условий.
- Семантическое сравнение условий if отложено. Сейчас сравнивается только точный текст соседних условий.
- Конструктор с `this()` или `super()` содержит непрозрачный вызов, CFG такого метода partial.
- Узлы графа нельзя редактировать: смысловая правка только через проверенный патч.

## Проверки

Из `backend` через `.venv`:

- `ruff format --check`, `ruff check`, `mypy` - без замечаний.
- `pytest` - 112 passed.
- `python -m app.openapi_export --check` - контракт совпадает с `contracts/openapi.json`.

## Не входит в этап

Java Runner, сравнение поведения, перестановка ребер CFG и серверный outline отдельным маршрутом.
