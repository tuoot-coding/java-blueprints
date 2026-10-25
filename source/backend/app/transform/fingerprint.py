"""Отпечаток исходника: sha256 UTF-8 в hex.

Это отдельный признак текста. Номер ревизии проекта - целое число в Storage.
Quick fix сверяет отпечаток, чтобы не применить правку к другому тексту.
"""

from __future__ import annotations

import hashlib


def source_fingerprint(source: str) -> str:
    """Возвращает sha256 hex дайджест UTF-8 байтов исходника."""
    return hashlib.sha256(source.encode("utf-8")).hexdigest()
