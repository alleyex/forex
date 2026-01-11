import threading
from typing import Optional


class ReactorManager:
    """
    Singleton manager for Twisted reactor.
    Ensures reactor runs in a single background thread.
    """
    
    _instance: Optional["ReactorManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "ReactorManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._initialized = True

    def ensure_running(self) -> None:
        """Start reactor thread if not already running"""
        if self._running:
            return
            
        with self._lock:
            if self._running:
                return
                
            from twisted.internet import reactor
            
            def run_reactor():
                reactor.run(installSignalHandlers=False)
            
            self._thread = threading.Thread(target=run_reactor, daemon=True)
            self._thread.start()
            self._running = True

    @property
    def is_running(self) -> bool:
        return self._running


# Global instance
reactor_manager = ReactorManager()