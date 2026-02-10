from __future__ import annotations

from forex.infrastructure.broker.ctrader.services.trendbar_history_service import TrendbarHistoryService


class _DummyClient:
    def send(self, _message):
        return None


class _DummyAppAuthService:
    def __init__(self) -> None:
        self._client = _DummyClient()

    def add_message_handler(self, _handler) -> None:
        return None

    def remove_message_handler(self, _handler) -> None:
        return None

    def get_client(self):
        return self._client


def test_default_window_respects_h1_timeframe() -> None:
    service = TrendbarHistoryService(_DummyAppAuthService())
    service.fetch(account_id=1, symbol_id=1, count=50, timeframe="H1")
    assert service._last_request_window == 3000


def test_default_window_respects_m5_timeframe() -> None:
    service = TrendbarHistoryService(_DummyAppAuthService())
    service.fetch(account_id=1, symbol_id=1, count=50, timeframe="M5")
    assert service._last_request_window == 250
