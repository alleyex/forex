from __future__ import annotations

from forex.infrastructure.broker.ctrader.services.trendbar_history_service import (
    TrendbarHistoryService,
)


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
    assert service._last_request_mode == "count_backfill"
    assert service._pending_request.fromTimestamp == service._MIN_TIMESTAMP_MS
    assert service._pending_request.count == 50


def test_default_window_respects_m5_timeframe() -> None:
    service = TrendbarHistoryService(_DummyAppAuthService())
    service.fetch(account_id=1, symbol_id=1, count=50, timeframe="M5")
    assert service._last_request_mode == "count_backfill"
    assert service._pending_request.fromTimestamp == service._MIN_TIMESTAMP_MS
    assert service._pending_request.count == 50


def test_explicit_time_range_keeps_window_mode() -> None:
    service = TrendbarHistoryService(_DummyAppAuthService())
    service.fetch(
        account_id=1,
        symbol_id=1,
        count=50,
        timeframe="M10",
        from_ts=1_700_000_000_000,
        to_ts=1_700_030_000_000,
    )
    assert service._last_request_mode == "milliseconds"
    assert service._pending_request.fromTimestamp == 1_700_000_000_000


def test_minimum_useful_bar_count_has_live_feature_floor() -> None:
    service = TrendbarHistoryService(_DummyAppAuthService())
    service._last_request_count = 220
    assert service._minimum_useful_bar_count() == 64
