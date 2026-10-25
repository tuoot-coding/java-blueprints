"""Проверка health endpoint для HEALTHCHECK контейнера: `python -m app.healthcheck`.

Код возврата 0 только при HTTP 200 и status == "ok".
"""

from __future__ import annotations

import json
import sys
import urllib.request

from app.core.config import get_settings
from app.core.metadata import API_V1_PREFIX

HEALTHCHECK_TIMEOUT_SECONDS = 3.0


def check_local_health(port: int, timeout_seconds: float) -> bool:
    url = f"http://127.0.0.1:{port}{API_V1_PREFIX}/health"
    try:
        with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
            if response.status != 200:
                return False
            body = json.loads(response.read())
    except (OSError, ValueError):
        return False
    return isinstance(body, dict) and body.get("status") == "ok"


if __name__ == "__main__":
    sys.exit(0 if check_local_health(get_settings().api_port, HEALTHCHECK_TIMEOUT_SECONDS) else 1)
