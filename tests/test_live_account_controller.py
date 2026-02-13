from __future__ import annotations

import time
from types import SimpleNamespace

from forex.config.constants import ConnectionStatus
from forex.ui.live.controllers.account_controller import LiveAccountController


class _SignalSink:
    def __init__(self) -> None:
        self.messages: list[str] = []
        self.payloads: list[object] = []

    def emit(self, payload) -> None:
        if isinstance(payload, str):
            self.messages.append(payload)
        else:
            self.payloads.append(payload)


class _FundsUseCaseStub:
    def __init__(self) -> None:
        self.in_progress = False
        self.fetch_calls: list[int] = []
        self._callbacks = {}

    def set_callbacks(self, **kwargs) -> None:
        self._callbacks = kwargs

    def fetch(self, account_id: int) -> None:
        self.fetch_calls.append(int(account_id))


class _UseCasesStub:
    def __init__(self, funds_uc: _FundsUseCaseStub) -> None:
        self._funds_uc = funds_uc
        self.create_calls = 0

    def create_account_funds(self, _service):
        self.create_calls += 1
        return self._funds_uc


def _make_window(*, transport_fresh: bool) -> SimpleNamespace:
    funds_uc = _FundsUseCaseStub()
    use_cases = _UseCasesStub(funds_uc)
    return SimpleNamespace(
        _account_authorization_blocked=False,
        _service=SimpleNamespace(
            status=int(ConnectionStatus.APP_AUTHENTICATED),
            is_transport_fresh=lambda max_idle_seconds=10.0: transport_fresh,
        ),
        _oauth_service=SimpleNamespace(status=int(ConnectionStatus.ACCOUNT_AUTHENTICATED)),
        _account_switch_in_progress=False,
        _app_state=SimpleNamespace(selected_account_id=46147438),
        _last_funds_fetch_ts=0.0,
        _use_cases=use_cases,
        _account_funds_uc=None,
        _auto_balance=None,
        _auto_peak_balance=None,
        _auto_day_key=None,
        _auto_day_balance=None,
        _position_pnl_by_id={},
        _open_positions=[],
        logRequested=_SignalSink(),
        accountSummaryUpdated=_SignalSink(),
    )


def test_refresh_account_balance_skips_when_transport_not_fresh() -> None:
    window = _make_window(transport_fresh=False)
    controller = LiveAccountController(window)

    controller.refresh_account_balance()

    assert window._account_funds_uc is None
    assert window._use_cases.create_calls == 0


def test_refresh_account_balance_requests_funds_when_transport_fresh() -> None:
    window = _make_window(transport_fresh=True)
    controller = LiveAccountController(window)

    controller.refresh_account_balance()

    funds_uc = window._account_funds_uc
    assert funds_uc is not None
    assert window._use_cases.create_calls == 1
    assert funds_uc.fetch_calls == [46147438]

    # Rate-limited within 4.5s; should not fetch again immediately.
    controller.refresh_account_balance()
    assert funds_uc.fetch_calls == [46147438]

    # After interval, fetch can run again.
    window._last_funds_fetch_ts = time.time() - 10.0
    controller.refresh_account_balance()
    assert funds_uc.fetch_calls == [46147438, 46147438]
