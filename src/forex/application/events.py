from collections import defaultdict
from collections.abc import Callable
from typing import Any


class EventBus:
    """Simple in-process event bus for app-level signals."""

    def __init__(self) -> None:
        self._subscribers: defaultdict[str, list[Callable[[Any], None]]] = defaultdict(list)

    def subscribe(self, event: str, handler: Callable[[Any], None]) -> None:
        self._subscribers[event].append(handler)

    def publish(self, event: str, payload: Any) -> None:
        for handler in list(self._subscribers.get(event, [])):
            handler(payload)
