from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from forex.ui.live.orchestration.autotrade_coordinator import LiveAutoTradeCoordinator


class _SpinBoxStub:
    def __init__(self, value: float) -> None:
        self._value = value

    def value(self) -> float:
        return self._value


class _CheckBoxStub:
    def __init__(self, checked: bool = False) -> None:
        self._checked = checked

    def isChecked(self) -> bool:
        return self._checked


class _OrderServiceStub:
    def __init__(self) -> None:
        self.in_progress = False
        self.place_calls: list[dict[str, object]] = []

    def place_market_order(self, **kwargs):
        self.place_calls.append(kwargs)
        return "order-1"


def _make_window() -> SimpleNamespace:
    return SimpleNamespace(
        _app_state=SimpleNamespace(selected_account_id=123),
        _trade_symbol=SimpleNamespace(currentText=lambda: "EURUSD"),
        _resolve_symbol_id=lambda _name: 1,
        _open_positions=[],
        _order_service=_OrderServiceStub(),
        _ensure_order_service=lambda: None,
        _auto_debug_log=lambda _message: None,
        _auto_debug_fields=lambda *_args, **_kwargs: None,
        _auto_log=lambda _message: None,
        _confidence=_SpinBoxStub(0.15),
        _position_step=_SpinBoxStub(0.05),
        _max_positions=_SpinBoxStub(3),
        _near_full_hold=_CheckBoxStub(True),
        _same_side_rebalance=_CheckBoxStub(True),
        _slippage_bps=_SpinBoxStub(0.1),
        _fee_bps=_SpinBoxStub(0.15),
        _lot_value=_SpinBoxStub(0.1),
        _lot_risk=_CheckBoxStub(False),
        _scale_lot_by_signal=_CheckBoxStub(False),
        _stop_loss=_SpinBoxStub(200),
        _take_profit=_SpinBoxStub(500),
        _auto_enabled=True,
        _auto_position=0.0,
        _auto_position_id=None,
        _auto_weekend_guard_enabled=True,
        _auto_weekend_cutoff_hour_utc=20,
        _auto_weekend_cutoff_minute_utc=0,
        _auto_weekend_resume_hour_utc=0,
        _auto_weekend_resume_minute_utc=0,
        _auto_last_weekend_guard_phase=None,
        _auto_balance=10000.0,
        _auto_used_margin=0.0,
        _auto_free_margin=10000.0,
        _auto_leverage=100.0,
        _auto_max_leverage=100.0,
        _auto_margin_usage_cap_ratio=0.5,
        _account_summary_labels={"currency": SimpleNamespace(text=lambda: "USD")},
        _symbol_volume_loaded=True,
        _symbol_volume_constraints={"EURUSD": (100000, 100000)},
        _symbol_overrides_loaded=True,
        _symbol_overrides={},
        _symbol_details_by_id={},
        _symbol_id_map={"EURUSD": 1},
        _symbol_id_to_name={1: "EURUSD"},
        _symbol_name="EURUSD",
        _quote_digits={"EURUSD": 5},
        _price_digits=5,
        _quote_last_mid={1: 1.1450},
        _quote_last_bid={1: 1.1449},
        _quote_last_ask={1: 1.1451},
        _candles=[],
        _fetch_symbol_details=lambda _symbol_name: None,
    )


def test_execute_target_position_allows_full_exposure_on_first_trade() -> None:
    window = _make_window()
    coordinator = LiveAutoTradeCoordinator(window)
    coordinator.refresh_account_balance = lambda: None
    coordinator.risk_guard_status = lambda: (True, "ok")
    coordinator.trade_cost_bps = lambda: 0.0
    coordinator.estimate_signal_edge_bps = lambda *_args, **_kwargs: 10.0

    did_execute = coordinator.execute_target_position(-1.0)

    assert did_execute is True
    assert window._auto_position == pytest.approx(-1.0)
    assert len(window._order_service.place_calls) == 1


def test_risk_percent_sizing_uses_balance_and_stop_loss_distance() -> None:
    window = _make_window()
    window._lot_risk = _CheckBoxStub(True)
    window._lot_value = _SpinBoxStub(1.0)
    coordinator = LiveAutoTradeCoordinator(window)

    volume = coordinator.calc_volume()

    assert volume == 5000000


def test_risk_percent_sizing_is_capped_by_margin_usage_limit() -> None:
    window = _make_window()
    window._lot_risk = _CheckBoxStub(True)
    window._lot_value = _SpinBoxStub(1.0)
    window._auto_balance = 100.0
    window._open_positions = [SimpleNamespace(positionId=1)]
    window._auto_used_margin = 49.0
    coordinator = LiveAutoTradeCoordinator(window)

    volume = coordinator.calc_volume()

    assert volume == 100000


def test_risk_percent_sizing_ignores_stale_used_margin_without_open_positions() -> None:
    window = _make_window()
    window._lot_risk = _CheckBoxStub(True)
    window._lot_value = _SpinBoxStub(0.3)
    window._auto_balance = 312.34
    window._auto_used_margin = 68.91
    coordinator = LiveAutoTradeCoordinator(window)

    preview = coordinator.estimate_lot_preview()

    assert preview["cap_applied"] is False
    assert preview["used_margin"] == pytest.approx(0.0)


def test_weekend_guard_blocks_new_trades_after_friday_cutoff() -> None:
    window = _make_window()
    coordinator = LiveAutoTradeCoordinator(window)

    blocked = coordinator._handle_weekend_guard(
        datetime(2026, 3, 20, 20, 5, tzinfo=timezone.utc)
    )

    assert blocked is True
    assert window._auto_last_weekend_guard_phase == "friday_flatten"


def test_weekend_guard_flattens_existing_positions_during_blocked_window() -> None:
    window = _make_window()
    window._open_positions = [SimpleNamespace(positionId=1)]
    window._auto_position = 0.5
    coordinator = LiveAutoTradeCoordinator(window)
    calls = {"targets": []}

    def _execute_target_position(target, feature_set=None) -> bool:
        calls["targets"].append(target)
        return True

    coordinator.execute_target_position = _execute_target_position

    blocked = coordinator._handle_weekend_guard(
        datetime(2026, 3, 21, 12, 0, tzinfo=timezone.utc)
    )

    assert blocked is True
    assert calls["targets"] == [0.0]
