from __future__ import annotations

from types import SimpleNamespace

from forex.config.constants import ConnectionStatus
from forex.ui.live.market_data_controller import LiveMarketDataController


class _DummyWindow:
    def __init__(self) -> None:
        self._timeframe = "M1"
        self._history_requested = True
        self._pending_history = True
        self._last_history_request_key = ("x",)
        self._last_history_success_key = ("y",)
        self._chart_frozen = False
        self._candles = [("old",)]
        self._oauth_service = SimpleNamespace(status=ConnectionStatus.ACCOUNT_AUTHENTICATED)
        self._app_state = SimpleNamespace(selected_account_id=123)
        self.stop_live_trendbar_calls = 0
        self.request_recent_history_calls = 0
        self.flush_calls = 0
        self.set_candles_calls: list[list] = []

    def _stop_live_trendbar(self) -> None:
        self.stop_live_trendbar_calls += 1

    def _request_recent_history(self) -> None:
        self.request_recent_history_calls += 1

    def _flush_chart_update(self) -> None:
        self.flush_calls += 1

    def set_candles(self, candles) -> None:
        self.set_candles_calls.append(list(candles))


def test_set_trade_timeframe_triggers_history_reload() -> None:
    window = _DummyWindow()
    controller = LiveMarketDataController(window)

    controller.set_trade_timeframe("M15")

    assert window._timeframe == "M15"
    assert window._history_requested is False
    assert window._pending_history is False
    assert window._last_history_request_key is None
    assert window._last_history_success_key is None
    assert window.stop_live_trendbar_calls == 1
    assert window._chart_frozen is True
    assert window._candles == []
    assert window.set_candles_calls == [[]]
    assert window.flush_calls == 1
    assert window.request_recent_history_calls == 1


def test_set_trade_timeframe_ignores_same_value() -> None:
    window = _DummyWindow()
    controller = LiveMarketDataController(window)

    controller.set_trade_timeframe("M1")

    assert window.stop_live_trendbar_calls == 0
    assert window.request_recent_history_calls == 0
