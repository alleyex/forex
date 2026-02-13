from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest

from forex.config.constants import ConnectionStatus
from forex.ui.live.session_orchestrator import LiveSessionOrchestrator, LiveSessionPhase


@dataclass
class _LogSink:
    messages: list[str] = field(default_factory=list)

    def emit(self, message: str) -> None:
        self.messages.append(str(message))


class _ToggleStub:
    def __init__(self, checked: bool = False) -> None:
        self._checked = bool(checked)
        self.set_checked_calls = 0

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, value: bool) -> None:
        self._checked = bool(value)
        self.set_checked_calls += 1


def _make_window(
    *,
    app_status: ConnectionStatus,
    oauth_status: ConnectionStatus,
    authorization_blocked: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        _service=SimpleNamespace(status=int(app_status)),
        _oauth_service=SimpleNamespace(status=int(oauth_status)),
        _account_authorization_blocked=authorization_blocked,
        logRequested=_LogSink(),
    )


@pytest.mark.parametrize(
    ("app_status", "oauth_status", "authorization_blocked", "expected"),
    [
        (
            ConnectionStatus.DISCONNECTED,
            ConnectionStatus.DISCONNECTED,
            True,
            LiveSessionPhase.LOCKOUT,
        ),
        (
            ConnectionStatus.CONNECTING,
            ConnectionStatus.DISCONNECTED,
            False,
            LiveSessionPhase.CONNECTING,
        ),
        (
            ConnectionStatus.DISCONNECTED,
            ConnectionStatus.DISCONNECTED,
            False,
            LiveSessionPhase.DISCONNECTED,
        ),
        (
            ConnectionStatus.CONNECTED,
            ConnectionStatus.DISCONNECTED,
            False,
            LiveSessionPhase.CONNECTING,
        ),
        (
            ConnectionStatus.APP_AUTHENTICATED,
            ConnectionStatus.DISCONNECTED,
            False,
            LiveSessionPhase.APP_READY,
        ),
        (
            ConnectionStatus.APP_AUTHENTICATED,
            ConnectionStatus.ACCOUNT_AUTHENTICATED,
            False,
            LiveSessionPhase.READY,
        ),
    ],
)
def test_sync_reconnect_phase_maps_statuses(
    app_status: ConnectionStatus,
    oauth_status: ConnectionStatus,
    authorization_blocked: bool,
    expected: LiveSessionPhase,
) -> None:
    window = _make_window(
        app_status=app_status,
        oauth_status=oauth_status,
        authorization_blocked=authorization_blocked,
    )
    orchestrator = LiveSessionOrchestrator(window)

    phase = orchestrator.sync_reconnect_phase(reason="test")

    assert phase == expected
    assert orchestrator.phase == expected


def test_sync_reconnect_phase_emits_transition_once_for_same_phase() -> None:
    window = _make_window(
        app_status=ConnectionStatus.APP_AUTHENTICATED,
        oauth_status=ConnectionStatus.ACCOUNT_AUTHENTICATED,
    )
    orchestrator = LiveSessionOrchestrator(window)

    first = orchestrator.sync_reconnect_phase(reason="first")
    second = orchestrator.sync_reconnect_phase(reason="second")

    assert first == LiveSessionPhase.READY
    assert second == LiveSessionPhase.READY
    assert len(window.logRequested.messages) == 1
    assert "to=READY" in window.logRequested.messages[0]


def test_handle_oauth_status_auto_checks_auto_trade_on_authenticated() -> None:
    toggle = _ToggleStub(checked=False)
    window = SimpleNamespace(
        _service=SimpleNamespace(status=int(ConnectionStatus.APP_AUTHENTICATED)),
        _oauth_service=SimpleNamespace(
            status=int(ConnectionStatus.ACCOUNT_AUTHENTICATED),
            last_authenticated_account_id=123,
            tokens=SimpleNamespace(account_id=123),
        ),
        _app_state=SimpleNamespace(selected_account_id=123, selected_account_scope=1),
        _accounts=[object()],
        _account_authorization_blocked=False,
        _account_switch_in_progress=False,
        _pending_full_reconnect=True,
        _auto_trade_toggle=toggle,
        _schedule_full_reconnect=lambda: None,
        _refresh_accounts=lambda: None,
        logRequested=_LogSink(),
    )
    orchestrator = LiveSessionOrchestrator(window)
    orchestrator.try_resume_runtime_loops = lambda **_kwargs: None

    orchestrator.handle_oauth_status(ConnectionStatus.ACCOUNT_AUTHENTICATED)

    assert toggle.isChecked() is True
    assert toggle.set_checked_calls == 1
    assert window._pending_full_reconnect is False


def test_handle_oauth_status_does_not_auto_check_for_view_only_scope() -> None:
    toggle = _ToggleStub(checked=False)
    window = SimpleNamespace(
        _service=SimpleNamespace(status=int(ConnectionStatus.APP_AUTHENTICATED)),
        _oauth_service=SimpleNamespace(
            status=int(ConnectionStatus.ACCOUNT_AUTHENTICATED),
            last_authenticated_account_id=123,
            tokens=SimpleNamespace(account_id=123),
        ),
        _app_state=SimpleNamespace(selected_account_id=123, selected_account_scope=0),
        _accounts=[object()],
        _account_authorization_blocked=False,
        _account_switch_in_progress=False,
        _pending_full_reconnect=False,
        _auto_trade_toggle=toggle,
        _schedule_full_reconnect=lambda: None,
        _refresh_accounts=lambda: None,
        logRequested=_LogSink(),
    )
    orchestrator = LiveSessionOrchestrator(window)
    orchestrator.try_resume_runtime_loops = lambda **_kwargs: None

    orchestrator.handle_oauth_status(ConnectionStatus.ACCOUNT_AUTHENTICATED)

    assert toggle.isChecked() is False
    assert toggle.set_checked_calls == 0
