"""Автотесты соответствия сгенерированного Java исходному: метрики и время.

Каждый тест печатает показатели сравнения (parse, методы, излишества, score, elapsed_ms).
"""

from __future__ import annotations

import time

import pytest

from app.services.code_compare import compare_generated_to_original, format_compare_report

# --- фикстуры: original vs "сгенерированный/оптимизированный" вариант ---

IDENTICAL = (
    "class A { int m(int x) { return x + 1; } }\n",
    "class A { int m(int x) { return x + 1; } }\n",
)

DECOMPOSED_LONG = (
    """
class SumBox {
  int heavy(int n) {
    int s = 0;
    for (int i = 0; i < n; i++) { s += i; }
    for (int i = 0; i < n; i++) { s += i * 2; }
    for (int i = 0; i < n; i++) { s += i * 3; }
    for (int i = 0; i < n; i++) { s += i * 4; }
    for (int i = 0; i < n; i++) { s += i * 5; }
    for (int i = 0; i < n; i++) { s += i * 6; }
    for (int i = 0; i < n; i++) { s += i * 7; }
    for (int i = 0; i < n; i++) { s += i * 8; }
    return s;
  }
}
""",
    """
class SumBox {
  int heavy(int n) {
    return part(n, 1) + part(n, 2) + part(n, 3) + part(n, 4)
         + part(n, 5) + part(n, 6) + part(n, 7) + part(n, 8);
  }
  private int part(int n, int k) {
    int s = 0;
    for (int i = 0; i < n; i++) { s += i * k; }
    return s;
  }
}
""",
)

DEDUPED = (
    """
class Twin {
  int left(int n) {
    int s = 0;
    for (int i = 0; i < n; i++) { s += i; }
    return s;
  }
  int right(int n) {
    int s = 0;
    for (int i = 0; i < n; i++) { s += i; }
    return s;
  }
}
""",
    """
class Twin {
  int left(int n) { return sum(n); }
  int right(int n) { return sum(n); }
  private int sum(int n) {
    int s = 0;
    for (int i = 0; i < n; i++) { s += i; }
    return s;
  }
}
""",
)

EQUALS_FIX = (
    """
class Eq {
  boolean same(String a, String b) { return a == b; }
}
""",
    """
class Eq {
  boolean same(String a, String b) { return a != null && a.equals(b); }
}
""",
)

NULL_ORDER = (
    """
class N {
  int len(String s) { return s.length(); }
}
""",
    """
class N {
  int len(String s) { return s == null ? 0 : s.length(); }
}
""",
)

COMPLEXITY_SPLIT = (
    """
class C {
  int f(int x) {
    if (x < 0) return -1;
    if (x == 0) return 0;
    if (x == 1) return 1;
    if (x == 2) return 2;
    if (x == 3) return 3;
    if (x == 4) return 4;
    if (x == 5) return 5;
    if (x == 6) return 6;
    if (x == 7) return 7;
    if (x == 8) return 8;
    if (x == 9) return 9;
    return x;
  }
}
""",
    """
class C {
  int f(int x) {
    if (x < 0) return -1;
    if (x <= 9) return x;
    return x;
  }
}
""",
)

PRESERVE_API = (
    """
class Api {
  public int run(int a, int b) { return a + b; }
}
""",
    """
class Api {
  public int run(int a, int b) { return add(a, b); }
  private int add(int a, int b) { return a + b; }
}
""",
)

MULTI_CLASS_SAFE = (
    """
class One { int x() { return 1; } }
""",
    """
class One { int x() { return 1; } }
""",
)

LOOP_OPT = (
    """
class L {
  boolean has(java.util.List<String> xs, String t) {
    for (int i = 0; i < xs.size(); i++) {
      if (xs.get(i) == t) return true;
    }
    return false;
  }
}
""",
    """
class L {
  boolean has(java.util.List<String> xs, String t) {
    for (String item : xs) {
      if (item != null && item.equals(t)) return true;
    }
    return false;
  }
}
""",
)

WHITESPACE_ONLY = (
    "class W{int m(){return 1;}}\n",
    "class W {\n  int m() {\n    return 1;\n  }\n}\n",
)


CASES = [
    ("identical", *IDENTICAL),
    ("decomposed_long", *DECOMPOSED_LONG),
    ("deduped", *DEDUPED),
    ("equals_fix", *EQUALS_FIX),
    ("null_order", *NULL_ORDER),
    ("complexity_split", *COMPLEXITY_SPLIT),
    ("preserve_api", *PRESERVE_API),
    ("multi_class_safe", *MULTI_CLASS_SAFE),
    ("loop_opt", *LOOP_OPT),
    ("whitespace_only", *WHITESPACE_ONLY),
]


@pytest.mark.parametrize("title,original,generated", CASES)
def test_generated_matches_original_contract(
    title: str,
    original: str,
    generated: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    started = time.perf_counter()
    metrics = compare_generated_to_original(original, generated)
    wall_ms = (time.perf_counter() - started) * 1000.0
    report = format_compare_report(metrics, title=title)
    print(report)
    print(f"wall_ms={wall_ms:.2f}")
    captured = capsys.readouterr()
    assert "elapsed_ms=" in captured.out
    assert "score=" in captured.out
    assert metrics.elapsed_ms >= 0
    assert metrics.original_parse_ok is True
    assert metrics.generated_parse_ok is True
    assert metrics.class_names_match is True
    assert metrics.public_methods_preserved is True
    assert metrics.passed is True
    assert metrics.score >= 0.75


def test_all_compare_cases_run_and_print_summary(capsys: pytest.CaptureFixture[str]) -> None:
    """Прогон всех сценариев подряд с итоговой сводкой времени и score."""
    rows: list[str] = []
    total_started = time.perf_counter()
    for title, original, generated in CASES:
        metrics = compare_generated_to_original(original, generated)
        assert metrics.passed, f"{title} failed: {metrics.report_lines}"
        rows.append(
            f"{title}: score={metrics.score:.3f} elapsed_ms={metrics.elapsed_ms:.2f} "
            f"methods={metrics.method_count_original}->{metrics.method_count_generated}"
        )
    total_ms = (time.perf_counter() - total_started) * 1000.0
    print("=== SUMMARY generated_vs_original ===")
    for row in rows:
        print(row)
    print(f"cases={len(rows)} total_elapsed_ms={total_ms:.2f}")
    out = capsys.readouterr().out
    assert "SUMMARY" in out
    assert f"cases={len(CASES)}" in out
