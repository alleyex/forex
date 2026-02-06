"""
Shared timeout helper for cTrader services.
"""
from __future__ import annotations

from typing import Callable, Optional
import threading

from forex.config.runtime import RetryPolicy


class TimeoutTracker:
    def __init__(self, on_timeout: Callable[[], None]):
        self._on_timeout = on_timeout
        self._timer: Optional[threading.Timer] = None
        self._policy: Optional[RetryPolicy] = None
        self._on_retry: Optional[Callable[[int], None]] = None
        self._attempt = 0
        self._timeout_seconds: Optional[float] = None

    def configure_retry(
        self,
        policy: Optional[RetryPolicy],
        on_retry: Optional[Callable[[int], None]],
    ) -> None:
        self._policy = policy
        self._on_retry = on_retry

    def start(self, timeout_seconds: Optional[float]) -> None:
        if not timeout_seconds:
            return
        self.cancel()
        self._attempt = 0
        self._timeout_seconds = float(timeout_seconds)
        self._schedule(self._timeout_seconds)

    def _schedule(self, delay: float) -> None:
        self._timer = threading.Timer(delay, self._handle_timeout)
        self._timer.daemon = True
        self._timer.start()

    def _handle_timeout(self) -> None:
        if self._policy and self._on_retry and self._attempt < self._policy.max_attempts:
            self._attempt += 1
            try:
                self._on_retry(self._attempt)
            finally:
                delay = self._policy.backoff_seconds or self._timeout_seconds or 0.0
                if delay > 0:
                    self._schedule(delay)
            return
        self._on_timeout()

    def cancel(self) -> None:
        if self._timer:
            self._timer.cancel()
            self._timer = None
        self._attempt = 0
