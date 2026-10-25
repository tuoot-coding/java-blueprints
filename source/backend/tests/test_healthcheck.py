from __future__ import annotations

import socket

from app.healthcheck import check_local_health


def _find_unused_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
    return port


def test_healthcheck_fails_when_server_is_not_listening() -> None:
    assert check_local_health(_find_unused_local_port(), timeout_seconds=0.5) is False
