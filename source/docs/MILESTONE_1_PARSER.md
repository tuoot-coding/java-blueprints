# Milestone 1 - Java Parser

Дата: 2026-10-24. Корень: `C:\Users\stasechka\java-blueprints`.

## Реализовано

- Зависимости: `tree-sitter==0.26.0`, `tree-sitter-java==0.23.5` (зафиксированы в `uv.lock`).
- Сервис `parse_java_source` (`backend/app/parser/service.py`).
- Адаптер Tree-sitter, сбор ERROR/missing, координаты UTF-16.
- HTTP `POST /api/v1/parser/parse`.
- Лимит `MAX_JAVA_SOURCE_BYTES` (по умолчанию 1 МиБ).
- Frontend: кнопка разбора, Diagnostics Panel, Monaco markers, защита от гонок запросов.
- OpenAPI обновлен через `python -m app.openapi_export`.

## Не реализовано (намеренно)

- Постоянный Storage проектов/ревизий.
- CFG / Analysis / Transform / Java Runner.
- Автопарсинг на каждый ввод.

## Проверки

- Backend: `pytest` 66 passed, ruff, mypy, openapi --check.
- Frontend: typecheck, lint, Vitest 13 passed, production build.
- Live API: valid -> `ok`; invalid -> `syntax_errors` + diagnostics; oversized -> 413; кириллица через node fetch -> `ok`.

## Следующий этап

Backend Milestone 2: Storage проектов + outline классов/методов либо CFG Builder по ARCHITECTURE.md.
