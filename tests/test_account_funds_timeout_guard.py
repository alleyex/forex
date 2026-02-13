from __future__ import annotations

from types import SimpleNamespace

from forex.config.constants import ConnectionStatus
from forex.infrastructure.broker.ctrader.services.account_funds_service import AccountFundsService


def test_on_timeout_cleans_up_silently_when_app_auth_not_ready(monkeypatch) -> None:
    service = AccountFundsService(SimpleNamespace(status=int(ConnectionStatus.CONNECTING)))
    service._in_progress = True

    calls = {"cleanup": 0, "emit_error": 0}
    monkeypatch.setattr(service, "_cleanup", lambda: calls.__setitem__("cleanup", calls["cleanup"] + 1))
    monkeypatch.setattr(service, "_emit_error", lambda _msg: calls.__setitem__("emit_error", calls["emit_error"] + 1))

    service._on_timeout()

    assert calls["cleanup"] == 1
    assert calls["emit_error"] == 0


def test_retry_request_cleans_up_when_app_auth_not_ready(monkeypatch) -> None:
    service = AccountFundsService(SimpleNamespace(status=int(ConnectionStatus.CONNECTING)))
    service._in_progress = True

    calls = {"cleanup": 0, "send": 0}
    monkeypatch.setattr(service, "_cleanup", lambda: calls.__setitem__("cleanup", calls["cleanup"] + 1))
    monkeypatch.setattr(service, "_send_initial_requests", lambda: calls.__setitem__("send", calls["send"] + 1))

    service._retry_request(attempt=1)

    assert calls["cleanup"] == 1
    assert calls["send"] == 0
