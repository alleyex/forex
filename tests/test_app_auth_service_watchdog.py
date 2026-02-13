from __future__ import annotations

import time

from forex.config.constants import ConnectionStatus
from forex.config.settings import AppCredentials
from forex.infrastructure.broker.ctrader.services.app_auth_service import AppAuthService


class _DummyClient:
    def send(self, *_args, **_kwargs):
        return None


def _make_service() -> AppAuthService:
    return AppAuthService(
        credentials=AppCredentials(host="demo", client_id="id", client_secret="secret"),
        host="demo.ctraderapi.com",
        port=5035,
    )


def test_handle_connected_resets_watchdog_window(monkeypatch) -> None:
    service = _make_service()
    client = _DummyClient()
    service._client = client

    calls = {"watchdog": 0, "heartbeat": 0, "send_auth": 0}

    monkeypatch.setattr(service, "_start_connect_watchdog", lambda: calls.__setitem__("watchdog", calls["watchdog"] + 1))
    monkeypatch.setattr(service, "_start_heartbeat_loop", lambda: calls.__setitem__("heartbeat", calls["heartbeat"] + 1))
    monkeypatch.setattr(service, "_send_app_auth", lambda _client: calls.__setitem__("send_auth", calls["send_auth"] + 1))

    service._handle_connected(client)

    assert calls["watchdog"] == 1
    assert calls["heartbeat"] == 1
    assert calls["send_auth"] == 1
    assert service._connect_started_ts is not None
    assert service.status == ConnectionStatus.CONNECTED


def test_connect_timeout_schedules_reconnect_when_client_exists_before_tcp_connected(monkeypatch) -> None:
    service = _make_service()
    service._status = ConnectionStatus.CONNECTING
    service._client = _DummyClient()

    calls = {"reason": None, "stopped": 0}
    logs: list[str] = []
    monkeypatch.setattr(service, "_stop_client_service", lambda *_args, **_kwargs: calls.__setitem__("stopped", calls["stopped"] + 1))
    monkeypatch.setattr(service, "_schedule_reconnect", lambda reason: calls.__setitem__("reason", reason))
    monkeypatch.setattr(service, "_log", lambda message: logs.append(str(message)))

    service._on_connect_timeout()

    assert calls["stopped"] == 1
    assert calls["reason"] == "連線逾時"
    assert any("連線逾時" in message for message in logs)
    assert service.status == ConnectionStatus.DISCONNECTED
    assert service._client is None


def test_connect_timeout_schedules_reconnect_when_client_exists_after_tcp_connected(monkeypatch) -> None:
    service = _make_service()
    service._status = ConnectionStatus.CONNECTED
    service._client = _DummyClient()

    calls = {"reason": None, "stopped": 0}
    logs: list[str] = []
    monkeypatch.setattr(service, "_stop_client_service", lambda *_args, **_kwargs: calls.__setitem__("stopped", calls["stopped"] + 1))
    monkeypatch.setattr(service, "_schedule_reconnect", lambda reason: calls.__setitem__("reason", reason))
    monkeypatch.setattr(service, "_log", lambda message: logs.append(str(message)))

    service._on_connect_timeout()

    assert calls["stopped"] == 1
    assert calls["reason"] == "App 認證逾時"
    assert any("App 認證逾時" in message for message in logs)
    assert service.status == ConnectionStatus.DISCONNECTED
    assert service._client is None


def test_connect_timeout_schedules_reconnect_when_no_client(monkeypatch) -> None:
    service = _make_service()
    service._status = ConnectionStatus.CONNECTING
    service._client = None

    calls = {"reason": None, "stopped": 0}
    monkeypatch.setattr(service, "_stop_client_service", lambda *_args, **_kwargs: calls.__setitem__("stopped", calls["stopped"] + 1))
    monkeypatch.setattr(service, "_schedule_reconnect", lambda reason: calls.__setitem__("reason", reason))
    monkeypatch.setattr(service, "_log", lambda _message: None)

    service._on_connect_timeout()

    assert calls["stopped"] == 1
    assert calls["reason"] == "連線逾時"


def test_handle_disconnected_skips_duplicate_schedule_when_reconnect_pending(monkeypatch) -> None:
    service = _make_service()
    client = _DummyClient()
    service._client = client
    service._status = ConnectionStatus.CONNECTED
    service._manual_disconnect = False
    service._auto_reconnect = True

    class _AliveTimer:
        @staticmethod
        def is_alive() -> bool:
            return True

    service._reconnect_timer = _AliveTimer()

    calls = {"scheduled": 0}
    monkeypatch.setattr(service, "_schedule_reconnect", lambda _reason: calls.__setitem__("scheduled", calls["scheduled"] + 1))
    monkeypatch.setattr(service, "_emit_error", lambda _err: None)
    monkeypatch.setattr(service, "_cancel_connect_watchdog", lambda: None)
    monkeypatch.setattr(service, "_cancel_app_auth_retry_timer", lambda: None)
    monkeypatch.setattr(service, "_stop_heartbeat_loop", lambda: None)
    monkeypatch.setattr(service, "clear_message_handlers", lambda: None)
    monkeypatch.setattr(service, "_end_operation", lambda: None)

    service._handle_disconnected(client, "test")

    assert calls["scheduled"] == 0


def test_transport_fresh_false_when_not_connected() -> None:
    service = _make_service()
    service._status = ConnectionStatus.DISCONNECTED
    service._last_message_ts = None

    assert service.seconds_since_last_message() is None
    assert service.is_transport_fresh() is False


def test_transport_fresh_uses_last_message_age() -> None:
    service = _make_service()
    service._status = ConnectionStatus.CONNECTED
    now = time.time()

    service._last_message_ts = now - 0.5
    assert service.is_transport_fresh(max_idle_seconds=1.0) is True

    service._last_message_ts = now - 2.0
    assert service.is_transport_fresh(max_idle_seconds=1.0) is False
