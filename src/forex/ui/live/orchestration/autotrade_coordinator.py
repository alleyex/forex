from __future__ import annotations

import json
import time
from dataclasses import replace
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOATradeSide

from forex.ml.rl.envs.trading_env import (
    TradingConfig,
    apply_risk_engine,
    build_window_observation,
    decode_policy_action,
)
from forex.ml.rl.features.feature_builder import build_features


class LiveAutoTradeCoordinator:
    """Encapsulates auto-trade decision and execution flow for LiveMainWindow."""

    def __init__(self, window) -> None:
        self._window = window

    def _effective_max_position(self) -> float:
        w = self._window
        try:
            configured = float(getattr(w, "_auto_env_max_position", 1.0))
        except Exception:
            configured = 1.0
        if configured <= 0.0:
            configured = 1.0
        return configured

    def _effective_min_position_change(self) -> float:
        w = self._window
        try:
            value = float(getattr(w, "_auto_env_min_position_change", 0.0))
        except Exception:
            value = 0.0
        return max(0.0, value)

    def _one_position_mode_enabled(self) -> bool:
        w = self._window
        control = getattr(w, "_one_position_mode", None)
        return bool(control and control.isChecked())

    def _effective_trading_config(self) -> TradingConfig:
        w = self._window
        base = getattr(w, "_auto_env_config", None)
        if not isinstance(base, TradingConfig):
            base = TradingConfig()
        step = float(base.position_step)
        if hasattr(w, "_position_step"):
            try:
                step = float(w._position_step.value())
            except Exception:
                step = float(base.position_step)
        return replace(
            base,
            max_position=self._effective_max_position(),
            min_position_change=self._effective_min_position_change(),
            position_step=step,
        )

    def run_auto_trade_on_close(self) -> None:
        w = self._window
        if not w._auto_enabled or not w._auto_model:
            return
        if not w._app_state or not w._app_state.selected_account_id:
            return
        if self._handle_weekend_guard():
            return
        config = self._effective_trading_config()
        min_bars_required = max(64, int(getattr(config, "window_size", 1)) + 16)
        w._auto_last_decision_ts = time.time()
        now_ts = datetime.utcnow().timestamp()
        min_interval = (
            int(w._min_signal_interval.value())
            if hasattr(w, "_min_signal_interval")
            else 0
        )
        if w._auto_last_action_ts and now_ts - w._auto_last_action_ts < min_interval:
            remain = max(0.0, min_interval - (now_ts - w._auto_last_action_ts))
            w._auto_debug_fields("signal_throttled", wait_s=f"{remain:.1f}")
            return
        if len(w._candles) < min_bars_required:
            w._auto_debug_fields(
                "insufficient_candles",
                have=len(w._candles),
                need=min_bars_required,
                window=int(getattr(config, "window_size", 1)),
            )
            w._request_recent_history(force=True)
            return

        df = pd.DataFrame(
            {
                "utc_timestamp_minutes": [int(c[0] // 60) for c in w._candles],
                "timestamp": [
                    datetime.utcfromtimestamp(c[0]).strftime("%Y-%m-%d %H:%M:%S")
                    for c in w._candles
                ],
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
            w._auto_debug_fields(
                "feature_rows_empty",
                candles=len(w._candles),
                need=min_bars_required,
                window=int(getattr(config, "window_size", 1)),
                scaler_features=len(getattr(w._auto_feature_scaler, "names", []) or []),
            )
            w._request_recent_history(force=True)
            return
        warmup_bars = max(0, int(getattr(w, "_auto_startup_warmup_bars", 0)))
        seen_bars = int(getattr(w, "_auto_startup_seen_bars", 0)) + 1
        w._auto_startup_seen_bars = seen_bars
        if seen_bars <= warmup_bars:
            w._auto_debug_fields(
                "startup_warmup",
                bars_seen=seen_bars,
                bars_needed=warmup_bars,
                candles=len(w._candles),
            )
            return
        max_position = max(1e-6, float(config.max_position))
        obs_idx = int(feature_set.features.shape[0] - 1)
        obs = build_window_observation(
            feature_set.features,
            obs_idx,
            position=w._auto_position,
            max_position=max_position,
            window_size=int(getattr(config, "window_size", 1)),
        )
        try:
            action, _ = w._auto_model.predict(obs, deterministic=True)
        except Exception as exc:
            w._auto_log(f"❌ Model inference failed: {exc}")
            return
        raw_action = decode_policy_action(action, config=config)
        equity = float(w._auto_balance) if w._auto_balance and float(w._auto_balance) > 0.0 else 1.0
        peak_equity = (
            float(w._auto_peak_balance)
            if w._auto_peak_balance and float(w._auto_peak_balance) > 0.0
            else equity
        )
        target_position, risk_info = apply_risk_engine(
            raw_action,
            current_position=float(w._auto_position),
            config=config,
            closes=np.asarray(feature_set.closes, dtype=np.float32),
            idx=obs_idx,
            equity=equity,
            peak_equity=peak_equity,
        )
        confidence_threshold = float(w._confidence.value()) if hasattr(w, "_confidence") else 0.0
        w._auto_debug_fields(
            "decision_input",
            tf=w._timeframe,
            candles=len(w._candles),
            features=int(feature_set.features.shape[1]),
            window=int(getattr(config, "window_size", 1)),
            pos=f"{w._auto_position:.3f}",
            action=f"{raw_action:.3f}",
            target=f"{target_position:.3f}",
            vol_scale=f"{risk_info['vol_target_scale']:.3f}",
            dd_scale=f"{risk_info['drawdown_governor_scale']:.3f}",
            confidence=f"{confidence_threshold:.3f}",
        )
        if confidence_threshold > 0 and abs(target_position) < confidence_threshold:
            w._auto_log(
                "ℹ️ Signal skipped by confidence: "
                f"|{target_position:.3f}| < {confidence_threshold:.3f}"
            )
        did_execute = self.execute_target_position(target_position, feature_set=feature_set)
        if did_execute:
            w._auto_last_action_ts = now_ts

    def _utc_now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _weekend_guard_phase(self, now: datetime | None = None) -> str:
        w = self._window
        if not bool(getattr(w, "_auto_weekend_guard_enabled", False)):
            return "trading_open"
        current = now or self._utc_now()
        current_utc = current.astimezone(timezone.utc)
        weekday = int(current_utc.weekday())
        hour_minute = (int(current_utc.hour), int(current_utc.minute))
        cutoff = (
            int(getattr(w, "_auto_weekend_cutoff_hour_utc", 20)),
            int(getattr(w, "_auto_weekend_cutoff_minute_utc", 0)),
        )
        resume = (
            int(getattr(w, "_auto_weekend_resume_hour_utc", 0)),
            int(getattr(w, "_auto_weekend_resume_minute_utc", 0)),
        )
        if weekday == 4 and hour_minute >= cutoff:
            return "friday_flatten"
        if weekday == 5 or weekday == 6:
            return "weekend_pause"
        if weekday == 0 and hour_minute < resume:
            return "weekend_pause"
        return "trading_open"

    def _handle_weekend_guard(self, now: datetime | None = None) -> bool:
        w = self._window
        phase = self._weekend_guard_phase(now)
        previous = getattr(w, "_auto_last_weekend_guard_phase", None)
        w._auto_last_weekend_guard_phase = phase
        if phase != previous:
            if phase == "friday_flatten":
                w._auto_log(
                    "ℹ️ Weekend guard active: no new trades after Friday cutoff; "
                    "existing positions will be flattened."
                )
            elif phase == "weekend_pause":
                w._auto_log("ℹ️ Weekend guard active: weekend trading is paused.")
            elif previous in {"friday_flatten", "weekend_pause"}:
                w._auto_startup_seen_bars = 0
                w._auto_last_action_ts = None
                w._auto_log(
                    "ℹ️ Weekend guard lifted: trading resumed; startup warmup has been reset."
                )
        if phase == "trading_open":
            return False
        has_positions = bool(
            getattr(w, "_open_positions", [])
            or getattr(w, "_auto_position_id", None)
        )
        if not has_positions and abs(float(getattr(w, "_auto_position", 0.0) or 0.0)) > 0.0:
            has_positions = True
        if has_positions:
            self.execute_target_position(0.0)
        return True

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

    def resolve_close_volume(
        self,
        position_id: int,
        *,
        desired_position: float | None = None,
        current_position: float | None = None,
    ) -> int:
        w = self._window
        position_volume: int | None = None
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
                position_volume = volume_int
            break

        if position_volume is None:
            fallback = self.calc_volume()
            w._auto_log(
                f"⚠️ Position {position_id} volume unavailable; fallback close volume={fallback}."
            )
            return fallback

        close_volume = position_volume
        if (
            desired_position is not None
            and current_position is not None
            and current_position != 0.0
            and desired_position * current_position > 0.0
            and abs(desired_position) < abs(current_position)
        ):
            keep_ratio = max(
                0.0,
                min(1.0, abs(desired_position) / abs(current_position)),
            )
            reduce_ratio = 1.0 - keep_ratio
            requested = int(round(position_volume * reduce_ratio))
            close_volume = self._normalize_close_volume(
                requested=requested,
                available=position_volume,
            )
            if close_volume <= 0:
                return 0
            w._auto_debug_fields(
                "partial_close_volume",
                available=position_volume,
                requested=requested,
                final=close_volume,
                keep_ratio=f"{keep_ratio:.3f}",
            )
            return close_volume

        return position_volume

    def _normalize_close_volume(self, *, requested: int, available: int) -> int:
        w = self._window
        symbol_name = (
            w._trade_symbol.currentText()
            if hasattr(w, "_trade_symbol")
            else w._symbol_name
        )
        min_volume, volume_step = self.get_volume_constraints(symbol_name)
        volume = max(0, int(requested))
        available = max(0, int(available))
        if volume <= 0 or available <= 0:
            return 0
        volume = min(volume, available)
        if volume_step > 1:
            volume = (volume // volume_step) * volume_step
        if volume <= 0:
            return 0
        if volume < min_volume:
            volume = min(min_volume, available)
            if volume_step > 1:
                volume = (volume // volume_step) * volume_step
        if volume <= 0:
            return 0
        if volume > available:
            volume = available
        remainder = available - volume
        if 0 < remainder < min_volume:
            adjusted = available - min_volume
            if adjusted <= 0:
                return available
            if volume_step > 1:
                adjusted = (adjusted // volume_step) * volume_step
            if adjusted <= 0:
                return available
            volume = adjusted
        return max(0, int(volume))

    def _resolve_full_close_volume(self, position_id: int) -> int:
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
        expected_side = (
            ProtoOATradeSide.BUY if side == "buy" else ProtoOATradeSide.SELL
        )
        symbol_name = (
            w._trade_symbol.currentText()
            if hasattr(w, "_trade_symbol")
            else w._symbol_name
        )
        count = 0
        for position in w._open_positions:
            trade_data = getattr(position, "tradeData", None)
            if not trade_data:
                continue
            pos_side = getattr(trade_data, "tradeSide", None)
            if not self._position_matches_symbol(
                position=position,
                symbol_id=symbol_id,
                symbol_name=symbol_name,
            ):
                continue
            if pos_side == expected_side:
                count += 1
        return count

    def count_open_positions_for_symbol(self, *, symbol_id: int) -> int:
        w = self._window
        symbol_name = (
            w._trade_symbol.currentText()
            if hasattr(w, "_trade_symbol")
            else w._symbol_name
        )
        count = 0
        for position in w._open_positions:
            if not self._position_matches_symbol(
                position=position,
                symbol_id=symbol_id,
                symbol_name=symbol_name,
            ):
                continue
            count += 1
        return count

    def execute_target_position(self, target: float, *, feature_set=None) -> bool:
        w = self._window
        if not w._app_state or not w._app_state.selected_account_id:
            return False
        account_id = int(w._app_state.selected_account_id)
        symbol_name = (
            w._trade_symbol.currentText()
            if hasattr(w, "_trade_symbol")
            else w._symbol_name
        )
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
        desired = float(
            np.clip(
                desired_raw,
                -self._effective_max_position(),
                self._effective_max_position(),
            )
        )
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
        one_position_mode = self._one_position_mode_enabled()
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

        if one_position_mode and symbol_count > 1:
            primary = self._select_symbol_primary_position(
                symbol_id=symbol_id,
                symbol_name=symbol_name,
            )
            primary_id = getattr(primary, "positionId", None) if primary is not None else None
            for position in list(w._open_positions):
                if not self._position_matches_symbol(
                    position=position,
                    symbol_id=symbol_id,
                    symbol_name=symbol_name,
                ):
                    continue
                position_id = getattr(position, "positionId", None)
                try:
                    position_id_int = int(position_id or 0)
                except (TypeError, ValueError):
                    position_id_int = 0
                if position_id_int <= 0:
                    continue
                try:
                    if primary_id is not None and int(primary_id) == position_id_int:
                        continue
                except (TypeError, ValueError):
                    pass
                volume = self._resolve_full_close_volume(position_id_int)
                w._auto_debug_fields(
                    "one_position_cleanup",
                    close_pos_id=position_id_int,
                    volume=volume,
                    open_symbol=symbol_count,
                )
                closed = w._order_service.close_position(
                    account_id=account_id,
                    position_id=position_id_int,
                    volume=volume,
                )
                if closed:
                    w._auto_log("ℹ️ One-position mode: cleaning extra same-symbol position.")
                return bool(closed)

        if desired == 0.0 and w._auto_position_id:
            volume = self._resolve_full_close_volume(int(w._auto_position_id))
            w._auto_debug_fields("close_position", pos_id=w._auto_position_id, volume=volume)
            closed = w._order_service.close_position(
                account_id=account_id,
                position_id=int(w._auto_position_id),
                volume=volume,
            )
            return bool(closed)

        if desired == 0.0:
            fallback_position = self._select_symbol_primary_position(
                symbol_id=symbol_id,
                symbol_name=symbol_name,
            )
            if fallback_position is not None:
                fallback_position_id = getattr(fallback_position, "positionId", None)
                try:
                    fallback_position_id_int = int(fallback_position_id or 0)
                except (TypeError, ValueError):
                    fallback_position_id_int = 0
                if fallback_position_id_int > 0:
                    w._auto_position_id = fallback_position_id_int
                    volume = self._resolve_full_close_volume(fallback_position_id_int)
                    w._auto_debug_fields(
                        "close_position_fallback",
                        pos_id=fallback_position_id_int,
                        volume=volume,
                    )
                    closed = w._order_service.close_position(
                        account_id=account_id,
                        position_id=fallback_position_id_int,
                        volume=volume,
                    )
                    return bool(closed)
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
            if one_position_mode:
                current_pos = float(w._auto_position)
                if abs(abs(desired) - abs(current_pos)) <= 0.05:
                    w._auto_position = desired
                    w._auto_debug_fields(
                        "one_position_hold_same_side",
                        current=f"{current_pos:.3f}",
                        desired=f"{desired:.3f}",
                    )
                    return False
                volume = self._resolve_full_close_volume(int(w._auto_position_id))
                w._auto_debug_fields(
                    "one_position_rebuild_same_side",
                    current=f"{current_pos:.3f}",
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
                    w._auto_log("ℹ️ One-position mode: closing current position before resizing.")
                return bool(closed)
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
                volume = self.resolve_close_volume(
                    int(w._auto_position_id),
                    desired_position=desired,
                    current_position=float(w._auto_position),
                )
                if volume <= 0:
                    w._auto_debug_log("same_side_rebalance: normalized close volume is zero")
                    return False
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
            volume = self._resolve_full_close_volume(int(w._auto_position_id))
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
        if volume <= 0:
            w._auto_log("ℹ️ Trade skipped by margin cap: no safe volume available.")
            return False
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

    def calc_volume(self, *, signal_strength: float | None = None) -> int:
        w = self._window
        lot = self._calculate_base_lot()
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
        if lot <= 0.0:
            return 0
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

    def _calculate_base_lot(self) -> float:
        w = self._window
        configured_value = float(w._lot_value.value())
        if not w._lot_risk.isChecked():
            return configured_value

        balance = getattr(w, "_auto_balance", None)
        if not balance or float(balance) <= 0.0:
            w._auto_log("⚠️ Balance unavailable; using fixed lot.")
            return configured_value

        stop_loss_points, _ = self.calc_sl_tp_pips()
        if not stop_loss_points or stop_loss_points <= 0:
            fallback_lot = max(0.01, (float(balance) * (configured_value / 100.0)) / 100000.0)
            w._auto_log("⚠️ Stop loss unavailable for risk sizing; using balance-percent fallback.")
            return fallback_lot

        point_value_per_lot = self._estimate_point_value_per_lot()
        if point_value_per_lot <= 0.0:
            fallback_lot = max(0.01, (float(balance) * (configured_value / 100.0)) / 100000.0)
            w._auto_log(
                "⚠️ Point value unavailable for risk sizing; "
                "using balance-percent fallback."
            )
            return fallback_lot

        risk_lot = self._estimate_risk_lot_only()
        margin_capped_lot, margin_meta = self._apply_margin_cap_to_lot(risk_lot)
        w._auto_debug_fields(
            "risk_sizing",
            balance=f"{float(balance):.2f}",
            risk_pct=f"{configured_value:.2f}",
            risk_amount=f"{float(balance) * (configured_value / 100.0):.2f}",
            stop_loss_points=stop_loss_points,
            point_value_per_lot=f"{point_value_per_lot:.4f}",
            risk_lot=f"{risk_lot:.4f}",
            margin_cap_lot=f"{margin_capped_lot:.4f}",
            final_lot=f"{margin_capped_lot:.4f}",
        )
        if margin_meta["cap_applied"]:
            w._auto_debug_fields(
                "margin_cap",
                balance=f"{margin_meta['balance']:.2f}",
                used_margin=f"{margin_meta['used_margin']:.2f}",
                max_used_margin=f"{margin_meta['max_used_margin']:.2f}",
                remaining_budget=f"{margin_meta['remaining_budget']:.2f}",
                leverage=f"{margin_meta['leverage']:.1f}",
                per_lot=f"{margin_meta['margin_per_lot']:.2f}",
                risk_lot=f"{risk_lot:.4f}",
                capped_lot=f"{margin_capped_lot:.4f}",
            )
        return margin_capped_lot

    def estimate_base_lot(self) -> float:
        return float(self._calculate_base_lot())

    def estimate_lot_preview(self) -> dict[str, float | bool | str]:
        w = self._window
        configured_value = float(w._lot_value.value())
        if not w._lot_risk.isChecked():
            return {
                "mode": "fixed",
                "configured_lot": configured_value,
                "final_lot": configured_value,
                "cap_applied": False,
            }
        risk_lot = self._estimate_risk_lot_only()
        final_lot, margin_meta = self._apply_margin_cap_to_lot(risk_lot)
        return {
            "mode": "risk",
            "risk_lot": risk_lot,
            "final_lot": final_lot,
            "cap_applied": bool(margin_meta["cap_applied"]),
            "balance": float(margin_meta["balance"]),
            "used_margin": float(margin_meta["used_margin"]),
            "max_used_margin": float(margin_meta["max_used_margin"]),
            "remaining_budget": float(margin_meta["remaining_budget"]),
            "stop_loss_points": float(self.calc_sl_tp_pips()[0]),
        }

    def _estimate_risk_lot_only(self) -> float:
        w = self._window
        configured_value = float(w._lot_value.value())
        balance = getattr(w, "_auto_balance", None)
        if not balance or float(balance) <= 0.0:
            return configured_value

        stop_loss_points, _ = self.calc_sl_tp_pips()
        if not stop_loss_points or stop_loss_points <= 0:
            return max(0.01, (float(balance) * (configured_value / 100.0)) / 100000.0)

        point_value_per_lot = self._estimate_point_value_per_lot()
        if point_value_per_lot <= 0.0:
            return max(0.01, (float(balance) * (configured_value / 100.0)) / 100000.0)

        risk_amount = float(balance) * (configured_value / 100.0)
        stop_loss_cost_per_lot = float(stop_loss_points) * point_value_per_lot
        if stop_loss_cost_per_lot <= 0.0:
            return max(0.01, (float(balance) * (configured_value / 100.0)) / 100000.0)
        return max(0.01, risk_amount / stop_loss_cost_per_lot)

    def _apply_margin_cap_to_lot(self, lot: float) -> tuple[float, dict[str, float | bool]]:
        w = self._window
        balance = float(getattr(w, "_auto_balance", None) or 0.0)
        open_positions = list(getattr(w, "_open_positions", []) or [])
        if open_positions:
            used_margin = max(0.0, float(getattr(w, "_auto_used_margin", None) or 0.0))
        else:
            used_margin = 0.0
        cap_ratio = max(
            0.0,
            min(1.0, float(getattr(w, "_auto_margin_usage_cap_ratio", 0.5))),
        )
        max_used_margin = max(0.0, balance * cap_ratio)
        remaining_budget = max_used_margin - used_margin
        margin_per_lot = self._estimate_margin_required_per_lot()
        leverage = self._effective_account_leverage()
        meta = {
            "balance": balance,
            "used_margin": used_margin,
            "max_used_margin": max_used_margin,
            "remaining_budget": remaining_budget,
            "margin_per_lot": margin_per_lot,
            "leverage": leverage,
            "cap_applied": False,
        }
        if lot <= 0.0:
            return 0.0, meta
        if balance <= 0.0 or margin_per_lot <= 0.0:
            return lot, meta
        if remaining_budget <= 0.0:
            meta["cap_applied"] = True
            return 0.0, meta
        margin_lot_cap = remaining_budget / margin_per_lot
        final_lot = max(0.0, min(float(lot), float(margin_lot_cap)))
        meta["cap_applied"] = final_lot + 1e-9 < float(lot)
        return final_lot, meta

    def _effective_account_leverage(self) -> float:
        w = self._window
        leverage = float(getattr(w, "_auto_leverage", None) or 0.0)
        if leverage > 0.0:
            return leverage
        max_leverage = float(getattr(w, "_auto_max_leverage", None) or 0.0)
        if max_leverage > 0.0:
            return max_leverage
        return 100.0

    def _estimate_margin_required_per_lot(self) -> float:
        w = self._window
        symbol_name = ""
        try:
            symbol_name = w._trade_symbol.currentText()
        except Exception:
            symbol_name = w._symbol_name
        symbol_name = str(symbol_name or "").strip().upper()
        if len(symbol_name) != 6:
            return 0.0

        base_currency = symbol_name[:3]
        account_currency = self._account_currency()
        leverage = self._effective_account_leverage()
        if leverage <= 0.0:
            return 0.0
        base_to_account = self._estimate_fx_conversion_rate(
            from_currency=base_currency,
            to_currency=account_currency,
        )
        if base_to_account <= 0.0:
            return 0.0
        contract_size = 100000.0
        notional_in_account = contract_size * base_to_account
        return notional_in_account / leverage

    def _estimate_point_value_per_lot(self) -> float:
        w = self._window
        symbol_name = ""
        try:
            symbol_name = w._trade_symbol.currentText()
        except Exception:
            symbol_name = w._symbol_name
        symbol_name = str(symbol_name or "").strip().upper()
        if len(symbol_name) != 6:
            return 0.0

        price = self._current_symbol_price(symbol_name)
        digits = int(w._quote_digits.get(symbol_name, w._price_digits or 5))
        point_size = 10 ** (-digits)
        contract_size = 100000.0
        quote_currency = symbol_name[3:]
        account_currency = self._account_currency()
        point_value_in_quote = contract_size * point_size

        if quote_currency == account_currency:
            return point_value_in_quote
        if price <= 0.0:
            return 0.0
        if symbol_name[:3] == account_currency:
            return point_value_in_quote / price

        conversion_rate = self._estimate_fx_conversion_rate(
            from_currency=quote_currency,
            to_currency=account_currency,
        )
        if conversion_rate > 0.0:
            return point_value_in_quote * conversion_rate
        return 0.0

    def _current_symbol_price(self, symbol_name: str) -> float:
        w = self._window
        symbol_id = w._symbol_id_map.get(symbol_name)
        if symbol_id is not None:
            mid = w._quote_last_mid.get(int(symbol_id))
            if mid and float(mid) > 0.0:
                return float(mid)
            bid = w._quote_last_bid.get(int(symbol_id))
            ask = w._quote_last_ask.get(int(symbol_id))
            if bid and ask:
                return (float(bid) + float(ask)) / 2.0
            if bid and float(bid) > 0.0:
                return float(bid)
            if ask and float(ask) > 0.0:
                return float(ask)
        if w._candles:
            try:
                return float(w._candles[-1][4])
            except Exception:
                return 0.0
        return 0.0

    def _account_currency(self) -> str:
        w = self._window
        label = getattr(w, "_account_summary_labels", {}).get("currency")
        if label is not None:
            try:
                text = str(label.text()).strip().upper()
            except Exception:
                text = ""
            if len(text) == 3:
                return text
        return "USD"

    def _estimate_fx_conversion_rate(self, *, from_currency: str, to_currency: str) -> float:
        w = self._window
        if from_currency == to_currency:
            return 1.0
        direct = f"{from_currency}{to_currency}"
        inverse = f"{to_currency}{from_currency}"
        for symbol_name, invert in ((direct, False), (inverse, True)):
            price = self._current_symbol_price(symbol_name)
            if price > 0.0:
                return (1.0 / price) if invert else price
            symbol_id = w._symbol_id_map.get(symbol_name)
            if symbol_id is not None:
                mid = w._quote_last_mid.get(int(symbol_id))
                if mid and float(mid) > 0.0:
                    return (1.0 / float(mid)) if invert else float(mid)
        return 0.0

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

    def calc_sl_tp_pips(self) -> tuple[int | None, int | None]:
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
            if self._position_matches_symbol(
                position=position,
                symbol_id=symbol_id,
                symbol_name=symbol_name,
            ):
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
        max_position = self._effective_max_position()
        side_sign = 0.0
        if side_value == ProtoOATradeSide.BUY:
            side_sign = 1.0
        elif side_value == ProtoOATradeSide.SELL:
            side_sign = -1.0
        if side_sign == 0.0:
            return

        # Infer normalized exposure from actual lot size when signal scaling is enabled.
        # This prevents stale +/-1.0 direction flags from forcing perpetual "reduce" logic.
        magnitude = max_position
        trade_volume = getattr(trade_data, "volume", None) if trade_data else None
        lot_value: float | None = None
        try:
            if trade_volume is not None:
                lot_value = float(trade_volume) / 10000000.0
        except (TypeError, ValueError):
            lot_value = None
        if lot_value is not None and lot_value > 0.0:
            base_lot = self._calculate_base_lot() if hasattr(w, "_lot_value") else 0.0
            if base_lot > 0.0:
                if getattr(w, "_scale_lot_by_signal", None) and w._scale_lot_by_signal.isChecked():
                    magnitude = min(max_position, max(0.0, lot_value / base_lot))
                else:
                    magnitude = max_position * min(
                        1.0,
                        max(0.0, lot_value / base_lot),
                    )
            else:
                magnitude = max_position

        w._auto_position = side_sign * float(magnitude)

    def _position_matches_symbol(
        self,
        *,
        position: object,
        symbol_id: int | None,
        symbol_name: str,
    ) -> bool:
        w = self._window
        trade_data = getattr(position, "tradeData", None)
        if not trade_data:
            return False
        pos_symbol_id = getattr(trade_data, "symbolId", None)
        try:
            pos_symbol_id_int = int(pos_symbol_id or 0)
        except (TypeError, ValueError):
            pos_symbol_id_int = 0

        if symbol_id is not None:
            try:
                if pos_symbol_id_int == int(symbol_id):
                    return True
            except (TypeError, ValueError):
                pass

        if symbol_name:
            resolved_name = w._symbol_id_to_name.get(pos_symbol_id_int, "")
            if isinstance(resolved_name, str) and resolved_name == symbol_name:
                return True
        return False

    def _select_symbol_primary_position(self, *, symbol_id: int, symbol_name: str):
        w = self._window
        matched = [
            p
            for p in w._open_positions
            if self._position_matches_symbol(
                position=p,
                symbol_id=symbol_id,
                symbol_name=symbol_name,
            )
        ]
        if not matched:
            return None
        return self.select_primary_position(matched)

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

    def refresh_account_balance(self) -> None:
        self._window._account_controller.refresh_account_balance()
