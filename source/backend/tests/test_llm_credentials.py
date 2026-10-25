from __future__ import annotations

from pathlib import Path

from app.llm.credentials import (
    extract_api_key_from_text,
    extract_gigachat_credentials,
    load_llm_api_key,
    load_llm_credentials,
)


def test_extract_gigachat_from_api_file_format() -> None:
    raw = """
Authorization Key MDFhMTZiY2MtNDhmMS03ZmRkLTllZDUtZTZkMWMzZDIyOWViOmY2ZWNiMDYzLWZiY2UtNGQxMC04OTg4LTQ4ZmY1MmVmOTg0Zg==
Client ID 01a16bcc-48f1-7fdd-9ed5-e6d1c3d229eb
Scope GIGACHAT_API_PERS
"""
    creds = extract_gigachat_credentials(raw)
    assert creds is not None
    assert creds.provider == "gigachat"
    assert creds.scope == "GIGACHAT_API_PERS"
    assert creds.client_id == "01a16bcc-48f1-7fdd-9ed5-e6d1c3d229eb"
    assert creds.authorization_key.startswith("MDFh")


def test_extract_legacy_openrouter_still_works() -> None:
    raw = """
curl https://openrouter.ai/api/v1/chat/completions \\
  -H "Authorization: Bearer sk-or-v1-abc123XYZ" \\
  -d '{}'
"""
    assert extract_api_key_from_text(raw) == "sk-or-v1-abc123XYZ"


def test_extract_plain_openrouter_key() -> None:
    assert extract_api_key_from_text("sk-or-v1-plainKey99") == "sk-or-v1-plainKey99"


def test_load_prefers_env_over_file(tmp_path: Path) -> None:
    key_file = tmp_path / "api"
    key_file.write_text(
        "Authorization Key filekeyfilekeyfilekeyfilekeyfile==\nScope GIGACHAT_API_PERS\n",
        encoding="utf-8",
    )
    creds = load_llm_credentials(env_key="envkeyenvkeyenvkeyenvkeyenvkey==", key_file=key_file)
    assert creds is not None
    assert creds.authorization_key == "envkeyenvkeyenvkeyenvkeyenvkey=="


def test_load_from_gigachat_file(tmp_path: Path) -> None:
    key_file = tmp_path / "api"
    key_file.write_text(
        "Authorization Key fileOnlyKeyfileOnlyKeyfileOnlyKey==\n"
        "Client ID 11111111-2222-3333-4444-555555555555\n"
        "Scope GIGACHAT_API_PERS\n",
        encoding="utf-8",
    )
    assert load_llm_api_key(env_key=None, key_file=key_file) == "fileOnlyKeyfileOnlyKeyfileOnlyKey=="
