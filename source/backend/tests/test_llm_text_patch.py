from __future__ import annotations

from app.llm.text_patch import apply_line_replacements


def test_apply_line_replacements_bottom_up() -> None:
    source = "a\nb\nc\nd\n"
    result = apply_line_replacements(
        source,
        [
            {"start_line": 2, "end_line": 2, "replacement": "B1\nB2"},
            {"start_line": 4, "end_line": 4, "replacement": "D"},
        ],
    )
    assert result == "a\nB1\nB2\nc\nD\n"


def test_extract_deepseek_credentials() -> None:
    from app.llm.credentials import extract_deepseek_credentials

    raw = """
Provider deepseek
API Key sk-abcdefghijklmnopqrstuv
Base URL https://api.deepseek.com
Model deepseek-chat
"""
    creds = extract_deepseek_credentials(raw)
    assert creds is not None
    assert creds.provider == "deepseek"
    assert creds.authorization_key.startswith("sk-")
    assert creds.model == "deepseek-chat"
