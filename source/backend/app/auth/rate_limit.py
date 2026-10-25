"""Rate limiting для login и password-reset с экспоненциальной блокировкой."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.auth.store import AuthStore
from app.core.errors import ApplicationError
from app.schemas.errors import ErrorCode


def assert_not_rate_limited(store: AuthStore, bucket_key: str) -> None:
    now = datetime.now(UTC)
    current = store.get_rate_limit(bucket_key)
    if current is None:
        return
    _fail_count, _window_started, blocked_until = current
    if blocked_until is not None and blocked_until > now:
        raise ApplicationError(ErrorCode.AUTH_RATE_LIMITED, status_code=429)


def register_auth_failure(
    store: AuthStore,
    bucket_key: str,
    *,
    max_failures: int,
    window_seconds: int,
) -> None:
    """Увеличивает счётчик; после порога включает экспоненциальную блокировку."""
    now = datetime.now(UTC)
    current = store.get_rate_limit(bucket_key)
    if current is None:
        store.upsert_rate_limit(
            bucket_key,
            fail_count=1,
            window_started_at=now,
            blocked_until=None,
        )
        return

    fail_count, window_started, blocked_until = current
    if blocked_until is not None and blocked_until > now:
        return
    if now - window_started > timedelta(seconds=window_seconds):
        store.upsert_rate_limit(
            bucket_key,
            fail_count=1,
            window_started_at=now,
            blocked_until=None,
        )
        return

    next_count = fail_count + 1
    next_block: datetime | None = None
    if next_count >= max_failures:
        # 2^(overflow) секунд, потолок 15 минут.
        overflow = next_count - max_failures + 1
        delay = min(15 * 60, 2**overflow)
        next_block = now + timedelta(seconds=delay)
    store.upsert_rate_limit(
        bucket_key,
        fail_count=next_count,
        window_started_at=window_started,
        blocked_until=next_block,
    )


def clear_auth_failures(store: AuthStore, bucket_key: str) -> None:
    store.clear_rate_limit(bucket_key)
