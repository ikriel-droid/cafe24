from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any, Callable, TypeVar

from app.core.config import get_settings

T = TypeVar("T")


class RateLimitExceededError(RuntimeError):
    def __init__(self, scope: str, *, retry_after_seconds: int, limit: int) -> None:
        super().__init__(f"Rate limit exceeded for {scope}. Retry after {retry_after_seconds} seconds.")
        self.scope = scope
        self.retry_after_seconds = retry_after_seconds
        self.limit = limit


class CircuitBreakerOpenError(RuntimeError):
    def __init__(self, service_name: str, operation_name: str, *, retry_after_seconds: int) -> None:
        super().__init__(
            f"Circuit breaker is open for {service_name}.{operation_name}. Retry after {retry_after_seconds} seconds."
        )
        self.service_name = service_name
        self.operation_name = operation_name
        self.retry_after_seconds = retry_after_seconds


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._lock = Lock()
        self._windows: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def check(self, *, scope: str, key: str, limit: int, window_seconds: int = 60) -> None:
        if limit <= 0:
            return

        now = time.monotonic()
        bucket_key = (scope, key)

        with self._lock:
            bucket = self._windows[bucket_key]
            cutoff = now - window_seconds
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= limit:
                retry_after = max(1, int(window_seconds - (now - bucket[0])))
                raise RateLimitExceededError(scope, retry_after_seconds=retry_after, limit=limit)

            bucket.append(now)

    def snapshot(self, policies: dict[str, tuple[int, int]]) -> list[dict[str, Any]]:
        now = time.monotonic()
        with self._lock:
            active_by_scope: dict[str, int] = {}
            for (scope, _key), bucket in list(self._windows.items()):
                window_seconds = policies.get(scope, (0, 60))[1]
                cutoff = now - window_seconds
                while bucket and bucket[0] <= cutoff:
                    bucket.popleft()
                if not bucket:
                    del self._windows[(scope, _key)]
                    continue
                active_by_scope[scope] = active_by_scope.get(scope, 0) + 1

        snapshot: list[dict[str, Any]] = []
        for scope, (limit, window_seconds) in policies.items():
            snapshot.append(
                {
                    "scope": scope,
                    "limit": limit,
                    "window_seconds": window_seconds,
                    "active_keys": active_by_scope.get(scope, 0),
                }
            )
        return snapshot

    def reset(self) -> None:
        with self._lock:
            self._windows.clear()


@dataclass
class _CircuitState:
    service_name: str
    failure_threshold: int
    recovery_seconds: int
    state: str = "closed"
    failure_count: int = 0
    opened_at: datetime | None = None
    last_failure_at: datetime | None = None
    last_success_at: datetime | None = None


class CircuitBreakerRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._circuits: dict[str, _CircuitState] = {}

    def execute(
        self,
        service_name: str,
        operation_name: str,
        callback: Callable[[], T],
        *,
        failure_threshold: int | None = None,
        recovery_seconds: int | None = None,
    ) -> T:
        settings = get_settings()
        failure_threshold = failure_threshold or settings.service_circuit_breaker_failure_threshold
        recovery_seconds = recovery_seconds or settings.service_circuit_breaker_recovery_seconds
        now = datetime.now(UTC)

        with self._lock:
            state = self._circuits.get(service_name)
            if state is None:
                state = _CircuitState(
                    service_name=service_name,
                    failure_threshold=failure_threshold,
                    recovery_seconds=recovery_seconds,
                )
                self._circuits[service_name] = state

            if state.state == "open" and state.opened_at is not None:
                retry_after = state.opened_at + timedelta(seconds=state.recovery_seconds)
                if now < retry_after:
                    raise CircuitBreakerOpenError(
                        service_name,
                        operation_name,
                        retry_after_seconds=max(1, int((retry_after - now).total_seconds())),
                    )
                state.state = "half_open"

        try:
            result = callback()
        except Exception:
            with self._lock:
                state = self._circuits[service_name]
                state.failure_count += 1
                state.last_failure_at = datetime.now(UTC)
                if state.failure_count >= state.failure_threshold:
                    state.state = "open"
                    state.opened_at = state.last_failure_at
            raise

        with self._lock:
            state = self._circuits[service_name]
            state.state = "closed"
            state.failure_count = 0
            state.opened_at = None
            state.last_success_at = datetime.now(UTC)
        return result

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {
                    "service_name": circuit.service_name,
                    "state": circuit.state,
                    "failure_count": circuit.failure_count,
                    "failure_threshold": circuit.failure_threshold,
                    "recovery_seconds": circuit.recovery_seconds,
                    "opened_at": circuit.opened_at,
                    "last_failure_at": circuit.last_failure_at,
                    "last_success_at": circuit.last_success_at,
                }
                for circuit in sorted(self._circuits.values(), key=lambda item: item.service_name)
            ]

    def reset(self) -> None:
        with self._lock:
            self._circuits.clear()


_rate_limiter = InMemoryRateLimiter()
_circuit_breaker_registry = CircuitBreakerRegistry()


def get_rate_limiter() -> InMemoryRateLimiter:
    return _rate_limiter


def get_circuit_breaker_registry() -> CircuitBreakerRegistry:
    return _circuit_breaker_registry


def reset_resilience_state() -> None:
    _rate_limiter.reset()
    _circuit_breaker_registry.reset()
