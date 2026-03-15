from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class AppState:
    """Shared application state for UI and use-cases."""
    app_status: int | None = None
    oauth_status: int | None = None
    selected_account_id: int | None = None
    selected_account_scope: int | None = None

    def __post_init__(self) -> None:
        self._listeners: list[Callable[[AppState], None]] = []

    def subscribe(self, handler: Callable[[AppState], None]) -> None:
        self._listeners.append(handler)

    def update_app_status(self, status: int) -> None:
        self.app_status = status
        self._notify()

    def update_oauth_status(self, status: int) -> None:
        self.oauth_status = status
        self._notify()

    def set_selected_account(self, account_id: int | None, scope: int | None = None) -> None:
        self.selected_account_id = account_id
        self.selected_account_scope = scope
        self._notify()

    def _notify(self) -> None:
        for handler in list(self._listeners):
            handler(self)
