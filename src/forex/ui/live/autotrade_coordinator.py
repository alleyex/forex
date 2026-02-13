from __future__ import annotations

from datetime import datetime
import json
import time
from typing import Optional

import numpy as np
import pandas as pd
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOATradeSide

from forex.ml.rl.features.feature_builder import build_features


class LiveAutoTradeCoordinator:
    """Encapsulates auto-trade decision and execution flow for LiveMainWindow."""

    def __init__(self, window) -> None:
        self._window = window

    def run_auto_trade_on_close(self) -> None:
        w = self._window
        if not w._auto_enabled or not w._auto_model:
            return
        if not w._app_state or not w._app_state.selected_account_id:
            return
        w._auto_last_decision_ts = time.time()
        now_ts = datetime.utcnow().timestamp()
        min_interval = int(w._min_signal_interval.value()) if hasattr(w, "_min_signal_interval") else 0
        if w._auto_last_action_ts and now_ts - w._auto_last_action_ts < min_interval:
            remain = max(0.0, min_interval - (now_ts - w._auto_last_action_ts))
            w._auto_debug_fields("signal_throttled", wait_s=f"{remain:.1f}")
            return
        if len(w._candles) < 30:
            w._auto_debug_fields("insufficient_candles", have=len(w._candles), need=30)
            return

        df = pd.DataFrame(
            {
                "timestamp": [datetime.utcfromtimestamp(c[0]).strftime("%H:%M") for c in w._candles],
                "open": [c[1] for c in w._candles],
                "high": [c[2] for c in w._candles],
                "low": [c[3] for c in w._candles],
                "close": [c[4] for c in w._candles],
            }
        )
        try:
            feature_set = build_features(df, scaler=w._auto_feature_scaler)
        except Exception as exc:
            w._auto_log(f"❌ Feature build failed: {exc}")
            return
        if feature_set.features.shape[0] <= 0:
            w._auto_debug_log("feature rows empty")
            return
        max_position = 1.0
        if hasattr(w, "_max_position"):
            try:
                max_position = float(w._max_position.value())
            except Exception:
                max_position = 1.0
        if max_position <= 0.0:
            max_position = 1.0
        position_norm = w._auto_position / max_position
        obs = np.concatenate(
            [feature_set.features[-1], np.array([position_norm], dtype=np.float32)]
        ).astype(np.float32)
        try:
            action, _ = w._auto_model.predict(obs, deterministic=True)
        except Exception as exc:
            w._auto_log(f"❌ Model inference failed: {exc}")
            return
        target_position = float(np.clip(action[0], -1.0, 1.0))
        confidence_threshold = float(w._confidence.value()) if hasattr(w, "_confidence") else 0.0
        w._auto_debug_fields(
            "decision_input",
            tf=w._timeframe,
            candles=len(w._candles),
            features=int(feature_set.features.shape[1]),
            pos=f"{w._auto_position:.3f}",
            action=f"{float(action[0]):.3f}",
            target=f"{target_position:.3f}",
            confidence=f"{confidence_threshold:.3f}",
        )
        if confidence_threshold > 0 and abs(target_position) < confidence_threshold:
            w._auto_log(
                f"ℹ️ Signal skipped by confidence: |{target_position:.3f}| < {confidence_threshold:.3f}"
            )
        did_execute = self.execute_target_position(target_position, feature_set=feature_set)
        if did_execute:
            w._auto_last_action_ts = now_ts

    def trade_cost_bps(self) -> float:
        w = self._window
        slippage_bps = float(w._slippage_bps.value()) if hasattr(w, "_slippage_bps") else 0.0
        fee_bps = float(w._fee_bps.value()) if hasattr(w, "_fee_bps") else 0.0
        return max(0.0, slippage_bps) + max(0.0, fee_bps)

    def estimate_signal_edge_bps(self, action_strength: float, feature_set=None) -> float:
        w = self._window
        strength = abs(float(action_strength))
        if strength <= 0:
            return 0.0
        if feature_set is not None:
            try:
                names = list(getattr(feature_set, "names", []) or [])
                if "atr_14" in names:
                    idx = names.index("atr_14")
                    atr_value = float(feature_set.features[-1][idx])
                    scaler = w._auto_feature_scaler
                    if scaler is not None:
                        try:
                            scaler_names = list(getattr(scaler, "names", []) or [])
                            if idx < len(scaler_names) and scaler_names[idx] == "atr_14":
                                std = float(scaler.stds[idx])
                                mean = float(scaler.means[idx])
                                if np.isfinite(std) and std != 0:
                                    atr_value = atr_value * std + mean
                                else:
                                    atr_value = mean
                        except Exception:
                            pass
                    if np.isfinite(atr_value) and atr_value > 0:
                        return strength * max(0.1, atr_value * 10000.0)
            except Exception:
                pass
        if not w._candles:
            return strength * 5.0
        window = w._candles[-14:]
        ranges: list[float] = []
        for _ts, _open, high, low, close in window:
            try:
                close_value = float(close)
                if close_value <= 0:
                    continue
                ranges.append(max(0.0, (float(high) - float(low)) / close_value))
            except Exception:
                continue
        if not ranges:
            return strength * 5.0
        atr_ratio = float(np.mean(ranges))
        atr_bps = max(0.1, atr_ratio * 10000.0)
        return strength * atr_bps

    def resolve_close_volume(self, position_id: int) -> int:
        w = self._window
        for position in w._open_positions:
            try:
                current_id = getattr(position, "positionId", None)
                if int(current_id or 0) != int(position_id):
                    continue
            except Exception:
                continue
            trade_data = getattr(position, "tradeData", None)
            volume = getattr(trade_data, "volume", None) if trade_data else None
            try:
                volume_int = int(volume)
            except (TypeError, ValueError):
                volume_int = 0
            if volume_int > 0:
                return volume_int
            break
        fallback = self.calc_volume()
        w._auto_log(
            f"⚠️ Position {position_id} volume unavailable; fallback close volume={fallback}."
        )
        return fallback

    def count_open_positions_for_symbol_side(self, *, symbol_id: int, desired_side: str) -> int:
        w = self._window
        side = str(desired_side or "").strip().lower()
        if side not in {"buy", "sell"}:
            return 0
        expected_side = ProtoOATradeSide.BUY if side == "buy" else ProtoOATradeSide.SELL
        count = 0
        for position in w._open_positions:
            trade_data = getattr(position, "tradeData", None)
            if not trade_data:
                continue
            pos_symbol_id = getattr(trade_data, "symbolId", None)
            pos_side = getattr(trade_data, "tradeSide", None)
            try:
                if int(pos_symbol_id or 0) != int(symbol_id):
                    continue
            except (TypeError, ValueError):
                continue
            if pos_side == expected_side:
                count += 1
        return count

    def count_open_positions_for_symbol(self, *, symbol_id: int) -> int:
        w = self._window
        count = 0
        for position in w._open_positions:
            trade_data = getattr(position, "tradeData", None)
            if not trade_data:
                continue
            pos_symbol_id = getattr(trade_data, "symbolId", None)
            try:
                if int(pos_symbol_id or 0) != int(symbol_id):
                    continue
            except (TypeError, ValueError):
                continue
            count += 1
        return count

    def apply_position_step(self, target: float) -> float:
        w = self._window
        step = 0.0
        if hasattr(w, "_position_step"):
            try:
                step = float(w._position_step.value())
            except Exception:
                step = 0.0
        value = float(np.clip(float(target), -1.0, 1.0))
        if step <= 0.0:
            return value
        stepped = round(value / step) * step
        if abs(stepped) < (step * 0.5):
            stepped = 0.0
        return float(np.clip(stepped, -1.0, 1.0))

    def execute_target_position(self, target: float, *, feature_set=None) -> bool:
        w = self._window
        if not w._app_state or not w._app_state.selected_account_id:
            return False
        account_id = int(w._app_state.selected_account_id)
        symbol_name = w._trade_symbol.currentText() if hasattr(w, "_trade_symbol") else w._symbol_name
        symbol_id = int(w._resolve_symbol_id(symbol_name))
        if w._open_positions:
            self.sync_auto_position_from_positions(w._open_positions)
        w._ensure_order_service()
        if not w._order_service or getattr(w._order_service, "in_progress", False):
            w._auto_debug_log("order service busy or unavailable; skip")
            return False
        self.refresh_account_balance()

        confidence_threshold = float(w._confidence.value()) if hasattr(w, "_confidence") else 0.0
        threshold = max(0.05, min(1.0, confidence_threshold))
        desired_raw = 0.0 if abs(target) < threshold else target
        desired = self.apply_position_step(desired_raw)
        desired_side = "buy" if desired > 0 else "sell"
        w._auto_debug_fields(
            "decision_normalized",
            threshold=f"{threshold:.3f}",
            target=f"{target:.3f}",
            desired_raw=f"{desired_raw:.3f}",
            desired=f"{desired:.3f}",
            step=f"{float(w._position_step.value()):.3f}",
            pos=f"{w._auto_position:.3f}",
            pos_id=w._auto_position_id,
        )
        max_positions = int(w._max_positions.value()) if hasattr(w, "_max_positions") else 1
        if max_positions <= 0:
            max_positions = 1
        near_full_hold_enabled = bool(
            getattr(w, "_near_full_hold", None) and w._near_full_hold.isChecked()
        )
        same_side_rebalance_enabled = bool(
            getattr(w, "_same_side_rebalance", None) and w._same_side_rebalance.isChecked()
        )
        same_side_count = self.count_open_positions_for_symbol_side(
            symbol_id=symbol_id,
            desired_side=desired_side,
        )
        symbol_count = self.count_open_positions_for_symbol(symbol_id=symbol_id)
        w._auto_debug_fields(
            "strategy_state",
            symbol=symbol_name,
            side=desired_side,
            desired=f"{desired:.3f}",
            open_same=same_side_count,
            open_symbol=symbol_count,
            cap=max_positions,
            near_full_hold=("ON" if near_full_hold_enabled else "OFF"),
            rebalance=("ON" if same_side_rebalance_enabled else "OFF"),
        )

        if desired == 0.0 and w._auto_position_id:
            volume = self.resolve_close_volume(int(w._auto_position_id))
            w._auto_debug_fields("close_position", pos_id=w._auto_position_id, volume=volume)
            closed = w._order_service.close_position(
                account_id=account_id,
                position_id=int(w._auto_position_id),
                volume=volume,
            )
            return bool(closed)

        if desired == 0.0:
            w._auto_position = 0.0
            w._auto_debug_log("no position change: desired flat and no open position")
            return False

        allowed, risk_reason = self.risk_guard_status()
        if not allowed:
            w._auto_log(f"⚠️ Risk guard blocked new trades. ({risk_reason})")
            return False

        allow_same_side_add = False
        if w._auto_position_id and (
            (w._auto_position > 0 and desired > 0)
            or (w._auto_position < 0 and desired < 0)
        ):
            # When desired exposure is weaker than current same-side exposure,
            # never add more. With rebalance OFF, hold; with rebalance ON,
            # try reducing first.
            current_pos = float(w._auto_position)
            if abs(desired) < (abs(current_pos) - 0.05):
                if not same_side_rebalance_enabled:
                    w._auto_position = desired
                    w._auto_debug_fields(
                        "same_side_hold_reduce_signal",
                        current=f"{current_pos:.3f}",
                        desired=f"{desired:.3f}",
                        rebalance="OFF",
                    )
                    return False
            if (
                same_side_rebalance_enabled
                and same_side_count > 0
                and abs(desired) < (abs(w._auto_position) - 0.05)
            ):
                volume = self.resolve_close_volume(int(w._auto_position_id))
                w._auto_debug_fields(
                    "same_side_rebalance_reduce",
                    current=f"{w._auto_position:.3f}",
                    desired=f"{desired:.3f}",
                    pos_id=w._auto_position_id,
                    volume=volume,
                )
                closed = w._order_service.close_position(
                    account_id=account_id,
                    position_id=int(w._auto_position_id),
                    volume=volume,
                )
                if closed:
                    w._auto_log("ℹ️ Same-side rebalance: reducing exposure before next signal.")
                    w._auto_position = desired
                return bool(closed)
            if near_full_hold_enabled and same_side_count > 0 and abs(desired) >= 0.95:
                w._auto_position = desired
                w._auto_debug_fields(
                    "same_side_hold_near_full",
                    desired=f"{desired:.3f}",
                    open=same_side_count,
                )
                return False
            if same_side_count >= max_positions:
                w._auto_position = desired
                w._auto_debug_fields(
                    "same_side_capped",
                    open=same_side_count,
                    cap=max_positions,
                )
                return False
            allow_same_side_add = True
            w._auto_position = desired
            w._auto_debug_fields("same_side_add_allowed", open=same_side_count, cap=max_positions)

        if w._auto_position_id and not allow_same_side_add:
            volume = self.resolve_close_volume(int(w._auto_position_id))
            w._auto_debug_fields("reverse_close_first", pos_id=w._auto_position_id, volume=volume)
            closed = w._order_service.close_position(
                account_id=account_id,
                position_id=int(w._auto_position_id),
                volume=volume,
            )
            if closed:
                w._auto_log("ℹ️ Closing existing position before reversing.")
            return bool(closed)

        estimated_edge_bps = self.estimate_signal_edge_bps(desired, feature_set=feature_set)
        total_cost_bps = self.trade_cost_bps()
        w._auto_debug_fields(
            "cost_check",
            edge_bps=f"{estimated_edge_bps:.2f}",
            cost_bps=f"{total_cost_bps:.2f}",
        )
        if total_cost_bps > 0 and estimated_edge_bps <= total_cost_bps:
            w._auto_log(
                "ℹ️ Trade skipped by cost filter: "
                f"edge {estimated_edge_bps:.2f} bps <= cost {total_cost_bps:.2f} bps."
            )
            return False

        volume = self.calc_volume(signal_strength=abs(desired))
        stop_loss_points, take_profit_points = self.calc_sl_tp_pips()
        w._auto_debug_fields(
            "place_order",
            side=desired_side,
            symbol=symbol_name,
            symbol_id=symbol_id,
            volume=volume,
            sl=stop_loss_points,
            tp=take_profit_points,
        )
        order_id = w._order_service.place_market_order(
            account_id=account_id,
            symbol_id=symbol_id,
            trade_side=desired_side,
            volume=volume,
            relative_stop_loss=stop_loss_points,
            relative_take_profit=take_profit_points,
            label="auto-ppo",
        )
        if not order_id:
            return False
        w._auto_position = desired
        return True

    def calc_volume(self, *, signal_strength: Optional[float] = None) -> int:
        w = self._window
        lot = float(w._lot_value.value())
        if w._lot_risk.isChecked():
            balance = w._auto_balance
            if balance:
                lot = max(0.01, (balance * (lot / 100.0)) / 100000.0)
            else:
                w._auto_log("⚠️ Balance unavailable; using fixed lot.")
        if (
            signal_strength is not None
            and hasattr(w, "_scale_lot_by_signal")
            and w._scale_lot_by_signal.isChecked()
        ):
            strength = max(0.0, min(1.0, float(signal_strength)))
            base_lot = lot
            lot = max(0.01, base_lot * strength)
            w._auto_debug_fields(
                "volume_scaling",
                base_lot=f"{base_lot:.4f}",
                strength=f"{strength:.3f}",
                scaled_lot=f"{lot:.4f}",
            )
        units = int(max(1, round(lot * 100000)))
        raw_volume = units * 100
        symbol_name = ""
        try:
            symbol_name = w._trade_symbol.currentText()
        except Exception:
            symbol_name = w._symbol_name
        w._fetch_symbol_details(symbol_name)
        min_volume, volume_step = self.get_volume_constraints(symbol_name)
        volume = max(raw_volume, min_volume)
        if volume_step > 1:
            volume = (volume // volume_step) * volume_step
            if volume < min_volume:
                volume = min_volume
        if volume != raw_volume:
            w._auto_log(
                f"⚠️ Volume adjusted {raw_volume} → {volume} (min {min_volume}, step {volume_step})."
            )
        return volume

    def get_volume_constraints(self, symbol_name: str) -> tuple[int, int]:
        w = self._window
        if not w._symbol_volume_loaded:
            self.load_symbol_volume_constraints()
        if symbol_name in w._symbol_volume_constraints:
            return w._symbol_volume_constraints[symbol_name]
        if not w._symbol_overrides_loaded:
            self.load_symbol_overrides()
        if symbol_name in w._symbol_overrides:
            override = w._symbol_overrides[symbol_name]
            min_volume = override.get("min_volume")
            volume_step = override.get("volume_step")
            try:
                min_volume_int = int(min_volume) if min_volume is not None else None
            except (TypeError, ValueError):
                min_volume_int = None
            try:
                volume_step_int = int(volume_step) if volume_step is not None else None
            except (TypeError, ValueError):
                volume_step_int = None
            if min_volume_int is not None or volume_step_int is not None:
                if min_volume_int is None:
                    min_volume_int = max(1, volume_step_int or 1)
                if volume_step_int is None:
                    volume_step_int = min_volume_int
                if min_volume_int > 0 and volume_step_int > 0:
                    w._symbol_volume_constraints[symbol_name] = (
                        min_volume_int,
                        volume_step_int,
                    )
                    return min_volume_int, volume_step_int
        symbol_id = w._symbol_id_map.get(symbol_name)
        if symbol_id is not None:
            detail = w._symbol_details_by_id.get(int(symbol_id))
            if isinstance(detail, dict):
                min_volume = detail.get("min_volume")
                volume_step = detail.get("volume_step")
                try:
                    min_volume_int = int(min_volume) if min_volume is not None else None
                except (TypeError, ValueError):
                    min_volume_int = None
                try:
                    volume_step_int = int(volume_step) if volume_step is not None else None
                except (TypeError, ValueError):
                    volume_step_int = None
                if min_volume_int is not None or volume_step_int is not None:
                    if min_volume_int is None:
                        min_volume_int = max(1, volume_step_int or 1)
                    if volume_step_int is None:
                        volume_step_int = min_volume_int
                    if min_volume_int > 0 and volume_step_int > 0:
                        w._symbol_volume_constraints[symbol_name] = (
                            min_volume_int,
                            volume_step_int,
                        )
                        return min_volume_int, volume_step_int
        return 100000, 100000

    def load_symbol_overrides(self) -> None:
        w = self._window
        w._symbol_overrides_loaded = True
        path = w._project_root / "symbol_overrides.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return
        if isinstance(data, dict):
            w._symbol_overrides = {str(k): v for k, v in data.items() if isinstance(v, dict)}

    def load_symbol_volume_constraints(self) -> None:
        w = self._window
        w._symbol_volume_loaded = True
        path = w._symbol_list_path()
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return
        for item in data:
            name = item.get("symbol_name")
            if not isinstance(name, str) or not name:
                continue
            min_volume = item.get("min_volume", item.get("minVolume"))
            volume_step = item.get("volume_step", item.get("volumeStep"))
            digits = item.get("digits")
            try:
                min_volume_int = int(min_volume) if min_volume is not None else None
            except (TypeError, ValueError):
                min_volume_int = None
            try:
                volume_step_int = int(volume_step) if volume_step is not None else None
            except (TypeError, ValueError):
                volume_step_int = None
            try:
                digits_int = int(digits) if digits is not None else None
            except (TypeError, ValueError):
                digits_int = None
            if min_volume_int is None and volume_step_int is None:
                if digits_int is None:
                    continue
            if min_volume_int is None:
                min_volume_int = max(1, volume_step_int or 1)
            if volume_step_int is None:
                volume_step_int = min_volume_int
            if min_volume_int <= 0 or volume_step_int <= 0:
                min_volume_int = None
                volume_step_int = None
            if min_volume_int is not None and volume_step_int is not None:
                w._symbol_volume_constraints[name] = (min_volume_int, volume_step_int)
            if digits_int is not None and digits_int > 0:
                w._symbol_digits_by_name[name] = digits_int
                w._quote_digits[name] = digits_int

    def calc_sl_tp_pips(self) -> tuple[Optional[int], Optional[int]]:
        w = self._window
        sl_points = float(w._stop_loss.value())
        tp_points = float(w._take_profit.value())
        stop_loss = None
        take_profit = None
        if sl_points > 0:
            stop_loss = int(round(sl_points))
        if tp_points > 0:
            take_profit = int(round(tp_points))
        return stop_loss, take_profit

    def sync_auto_position_from_positions(self, positions: list[object]) -> None:
        w = self._window
        if not w._auto_enabled:
            return
        symbol_name = ""
        try:
            symbol_name = w._trade_symbol.currentText()
        except Exception:
            symbol_name = w._symbol_name
        symbol_id = w._resolve_symbol_id(symbol_name) if symbol_name else None
        matched = []
        for position in positions:
            trade_data = getattr(position, "tradeData", None)
            pos_symbol_id = getattr(trade_data, "symbolId", None) if trade_data else None
            if symbol_id is not None and pos_symbol_id is not None and int(pos_symbol_id) != int(symbol_id):
                continue
            matched.append(position)
        if not matched:
            w._auto_position_id = None
            w._auto_position = 0.0
            return
        primary = self.select_primary_position(matched)
        trade_data = getattr(primary, "tradeData", None)
        side_value = getattr(trade_data, "tradeSide", None) if trade_data else None
        position_id = getattr(primary, "positionId", None)
        if position_id:
            w._auto_position_id = int(position_id)
        if side_value == ProtoOATradeSide.BUY:
            w._auto_position = 1.0
        elif side_value == ProtoOATradeSide.SELL:
            w._auto_position = -1.0

    @staticmethod
    def select_primary_position(positions: list[object]):
        def _sort_key(position: object) -> tuple[int, int]:
            trade_data = getattr(position, "tradeData", None)
            open_ts = getattr(trade_data, "openTimestamp", None) if trade_data else None
            pos_id = getattr(position, "positionId", None)
            try:
                open_ts_int = int(open_ts or 0)
            except (TypeError, ValueError):
                open_ts_int = 0
            try:
                pos_id_int = int(pos_id or 0)
            except (TypeError, ValueError):
                pos_id_int = 0
            return open_ts_int, pos_id_int

        return max(positions, key=_sort_key)

    def risk_guard_status(self) -> tuple[bool, str]:
        w = self._window
        if not w._risk_guard.isChecked():
            return True, "disabled"
        if w._auto_balance is None or w._auto_peak_balance is None or w._auto_day_balance is None:
            return True, "insufficient_balance_state"
        max_dd = float(w._max_drawdown.value()) / 100.0
        daily_loss = float(w._daily_loss.value()) / 100.0
        if w._auto_peak_balance > 0:
            drawdown = (w._auto_peak_balance - w._auto_balance) / w._auto_peak_balance
            if drawdown >= max_dd > 0:
                return False, f"max_drawdown {drawdown*100:.2f}% >= {max_dd*100:.2f}%"
        if w._auto_day_balance > 0:
            day_loss_ratio = (w._auto_day_balance - w._auto_balance) / w._auto_day_balance
            if day_loss_ratio >= daily_loss > 0:
                return False, f"daily_loss {day_loss_ratio*100:.2f}% >= {daily_loss*100:.2f}%"
        return True, "ok"

    def risk_guard_allows(self) -> bool:
        return self.risk_guard_status()[0]

    def refresh_account_balance(self) -> None:
        self._window._account_controller.refresh_account_balance()
