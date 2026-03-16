"""
Shared timeout helper for cTrader services.
"""
from __future__ import annotations

import threading
from collections.abc import Callable

from forex.config.runtime import RetryPolicy


class TimeoutTracker:
    def __init__(self, on_timeout: Callable[[], None]):
        self._on_timeout = on_timeout
        self._timer: threading.Timer | None = None
        self._policy: RetryPolicy | None = None
        self._on_retry: Callable[[int], None] | None = None
        self._attempt = 0
        self._timeout_seconds: float | None = None
        self._generation = 0

    def configure_retry(
        self,
        policy: RetryPolicy | None,
        on_retry: Callable[[int], None] | None,
    ) -> None:
        self._policy = policy
        self._on_retry = on_retry

    def start(self, timeout_seconds: float | None) -> None:
        if not timeout_seconds:
            return
        self.cancel()
        self._attempt = 0
        self._timeout_seconds = float(timeout_seconds)
        self._generation += 1
        self._schedule(self._timeout_seconds, self._generation)

    def _schedule(self, delay: float, generation: int) -> None:
        self._timer = threading.Timer(delay, self._handle_timeout, args=(generation,))
        self._timer.daemon = True
        self._timer.start()

    def _handle_timeout(self, generation: int) -> None:
        if generation != self._generation:
            return
        if self._policy and self._on_retry and self._attempt < self._policy.max_attempts:
            self._attempt += 1
            try:
                self._on_retry(self._attempt)
            finally:
                delay = self._policy.backoff_seconds or self._timeout_seconds or 0.0
                if delay > 0 and generation == self._generation:
                    self._schedule(delay, generation)
            return
        self._on_timeout()

    def cancel(self) -> None:
        if self._timer:
            self._timer.cancel()
            self._timer = None
        self._attempt = 0
        self._generation += 1
