"""
Shared timeout helper for cTrader services.
"""
from typing import Callable, Optional
import threading


class TimeoutTracker:
    def __init__(self, on_timeout: Callable[[], None]):
        self._on_timeout = on_timeout
        self._timer: Optional[threading.Timer] = None

    def start(self, timeout_seconds: Optional[int]) -> None:
        if not timeout_seconds:
            return
        self.cancel()
        self._timer = threading.Timer(timeout_seconds, self._on_timeout)
        self._timer.daemon = True
        self._timer.start()

    def cancel(self) -> None:
        if self._timer:
            self._timer.cancel()
            self._timer = None
