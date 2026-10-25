# Поддержка Java в IR / схеме / анализе

Дата: 2026-10-24. Источник истины - tree-sitter-java + структурный IR (`backend/app/ir`).

«Поддержано» значит: конструкция разбирается в IR без `unsupported`, попадает в модульную схему
и доступна статическому анализу. Это не семантика JVM и не javac.

## Базовый ТЗ (язык, I/O, коллекции, исключения)

См. фикстуру `fixtures/java/tz_java_lang_io_collections.java`.

| Тема | Статус |
| --- | --- |
| Классы / интерфейсы, примитивы, массивы, if/switch/циклы, методы, try/throw | да |
| System.in/out/err, Scanner, Formatter, printf, StandardCharsets | да |
| List/Set/Map и реализации, Iterator, Optional, `*.of` | да |
| throws, catch, multi-catch, свои исключения | да |

## Расширенный ТЗ

Фикстура: `fixtures/java/tz_advanced_java.java`.

| Тема | Статус | Как представлено |
| --- | --- | --- |
| record и enum | да | `record_declaration` (+ компоненты, compact ctor), `enum_declaration` + `enum_constant` |
| дженерики | да | `type_parameters` / `type_arguments` / `generic_type` в `type_text` и дочерних узлах |
| лямбды и java.util.function | да | `lambda_expression`; Function/Predicate/... как типы + вызовы |
| Stream API и Collectors | да | цепочки `method_invocation` (`stream`, `map`, `filter`, `collect`) |
| многопоточность / java.util.concurrent | да | `ExecutorService`, `Future`, `ConcurrentHashMap` через API-вызовы + лямбды |
| рефлексия | да | `class_literal` (`String.class`) + `Method`/`Field` вызовы |
| файлы / java.nio.file | да | `Path`/`Paths`/`Files` через вызовы |
| сеть | да | `URI`/`URL`/`InetAddress` через вызовы |
| java.time | да | `LocalDateTime`/`Duration`/`Instant`/`DateTimeFormatter` через вызовы |

Отдельных «магических» узлов Stream/Thread нет: библиотечные API моделируются как обычный Java-синтаксис.

## Ограничения

- Нет исполнения `javac`/`java` внутри backend-контейнера по умолчанию.
- Анонимные классы (`new Type() { ... }`) - `unsupported` (фикстура `unsupported_anonymous.java`).
- CFG для try / try-with-resources / do / for-each - непрозрачный шаг (`partial`).
- Анализ не моделирует семантику Stream/concurrency/reflection (только структура AST/IR).

## Проверка

```text
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_ir_tz_coverage.py tests/test_ir_advanced_java.py -q
```
