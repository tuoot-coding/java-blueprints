from __future__ import annotations

import pytest

from app.parser.models import ParseStatus
from app.parser.service import parse_java_source

VALID_EMPTY_CLASS = "class Empty {}\n"
VALID_METHOD = """
public class Demo {
  public int add(int left, int right) {
    return left + right;
  }
}
"""
VALID_IF = """
class Branch {
  void run(boolean flag) {
    if (flag) {
      return;
    }
  }
}
"""
VALID_LOOP = """
class Loop {
  void run(int n) {
    for (int i = 0; i < n; i++) {
      System.out.println(i);
    }
  }
}
"""
VALID_COMMENTS_STRINGS = """
class Notes {
  // однострочный
  /* блок */
  String text = "привет";
}
"""
VALID_CYRILLIC = """
class Пример {
  void метод() {
    String значение = "кириллица";
  }
}
"""
INVALID_MISSING_BRACE = "class Broken { void m() { int x = 1; "
INVALID_INCOMPLETE_METHOD = "class Broken { void m( "
INVALID_BAD_STMT = """
class Broken {
  void m() {
    int = ;
  }
}
"""


@pytest.mark.parametrize(
    "source",
    [
        VALID_EMPTY_CLASS,
        VALID_METHOD,
        VALID_IF,
        VALID_LOOP,
        VALID_COMMENTS_STRINGS,
        VALID_CYRILLIC,
    ],
)
def test_valid_java_parses_without_syntax_errors(source: str) -> None:
    result = parse_java_source(source)
    assert result.status == ParseStatus.OK
    assert result.has_syntax_errors is False
    assert result.diagnostics == ()
    assert result.root.type == "program"
    assert result.source is source
    assert result.source_byte_length == len(source.encode("utf-8"))


def test_empty_source_is_parseable() -> None:
    result = parse_java_source("")
    assert result.root.type == "program"
    assert result.source == ""
    assert result.source_byte_length == 0


@pytest.mark.parametrize(
    "source",
    [INVALID_MISSING_BRACE, INVALID_INCOMPLETE_METHOD, INVALID_BAD_STMT],
)
def test_invalid_java_returns_diagnostics_without_raising(source: str) -> None:
    result = parse_java_source(source)
    assert result.status == ParseStatus.SYNTAX_ERRORS
    assert result.has_syntax_errors is True
    assert len(result.diagnostics) >= 1
    for item in result.diagnostics:
        assert item.start_line >= 1
        assert item.start_column >= 1
        assert item.end_line >= 1
        assert item.end_column >= 1


def test_crlf_source_preserved_and_parsed() -> None:
    source = "class A {\r\n}\r\n"
    result = parse_java_source(source)
    assert result.source == source
    assert result.status == ParseStatus.OK


def test_parser_does_not_mutate_source_object() -> None:
    source = "class A {}"
    before = source
    result = parse_java_source(source)
    assert source == before
    assert result.source == before
