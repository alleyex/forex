from __future__ import annotations

import threading


class ReactorManager:
    """Singleton manager for the Twisted reactor."""

    _instance: ReactorManager | None = None
    _lock = threading.Lock()

    def __new__(cls) -> ReactorManager:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        self._thread: threading.Thread | None = None
        self._running = False
        self._initialized = True

    def ensure_running(self) -> None:
        """Start the reactor thread if not already running."""
        if self._running:
            return

        with self._lock:
            if self._running:
                return

            from twisted.internet import reactor

            def run_reactor() -> None:
                reactor.run(installSignalHandlers=False)

            self._thread = threading.Thread(target=run_reactor, daemon=True)
            self._thread.start()
            self._running = True


reactor_manager = ReactorManager()
