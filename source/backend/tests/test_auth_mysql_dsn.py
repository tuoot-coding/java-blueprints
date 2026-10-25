from __future__ import annotations

import pytest

from app.auth.mysql_store import parse_mysql_dsn


def test_parse_mysql_dsn() -> None:
    params = parse_mysql_dsn("mysql://jb:secret@db:3307/auth_db")
    assert params["host"] == "db"
    assert params["port"] == 3307
    assert params["user"] == "jb"
    assert params["password"] == "secret"
    assert params["database"] == "auth_db"


def test_parse_mysql_dsn_rejects_invalid() -> None:
    with pytest.raises(ValueError):
        parse_mysql_dsn("postgres://x")
