from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from forex.ml.rl.envs.trading_config_io import load_trading_config
from forex.ml.rl.envs.trading_env import (
    TradingConfig,
    apply_risk_engine,
    compute_drawdown,
    compute_horizon_return,
    compute_one_bar_return,
    simulate_step_transition,
)
from forex.ml.rl.features.feature_builder import (
    apply_scaler,
    build_feature_frame,
    filter_feature_rows_by_session,
    fit_scaler,
    load_csv,
    select_feature_columns,
)
from forex.tools.rl.run_live_sim import PlaybackResult, print_playback_result
from forex.utils.metrics import compute_sharpe_ratio_from_equity


def _parse_gate_specs(raw_specs: list[str], *, arg_name: str) -> list[dict[str, float | str | None]]:
    gates: list[dict[str, float | str | None]] = []
    for raw_spec in raw_specs:
        spec = str(raw_spec).strip()
        if not spec:
            continue
        parts = spec.split(":")
        if len(parts) != 3:
            raise ValueError(
                f"{arg_name} must use feature:min:max format, e.g. pre_london_compression:0.6:"
            )
        name = parts[0].strip()
        if not name:
            raise ValueError(f"{arg_name} requires a feature name")
        min_value = float(parts[1]) if parts[1].strip() else None
        max_value = float(parts[2]) if parts[2].strip() else None
        if min_value is not None and max_value is not None and min_value > max_value:
            raise ValueError(f"{arg_name} has min > max for {name}")
        gates.append({"feature": name, "min": min_value, "max": max_value})
    return gates


def _parse_feature_gate_specs(raw_specs: list[str]) -> list[dict[str, float | str | None]]:
    return _parse_gate_specs(raw_specs, arg_name="--feature-gate")


def _parse_action_gate_specs(raw_specs: list[str]) -> list[dict[str, float | str | None]]:
    return _parse_gate_specs(raw_specs, arg_name="--action-gate")


def _parse_threshold_bump_specs(raw_specs: list[str]) -> list[dict[str, float | str | None]]:
    bumps: list[dict[str, float | str | None]] = []
    for raw_spec in raw_specs:
        spec = str(raw_spec).strip()
        if not spec:
            continue
        parts = spec.split(":")
        if len(parts) != 4:
            raise ValueError(
                "--threshold-bump must use feature:min:max:bump format, e.g. volatility_regime_z:0.8::0.05"
            )
        name = parts[0].strip()
        if not name:
            raise ValueError("--threshold-bump requires a feature name")
        min_value = float(parts[1]) if parts[1].strip() else None
        max_value = float(parts[2]) if parts[2].strip() else None
        bump_value = float(parts[3]) if parts[3].strip() else 0.0
        if min_value is not None and max_value is not None and min_value > max_value:
            raise ValueError(f"--threshold-bump has min > max for {name}")
        if bump_value < 0.0:
            raise ValueError(f"--threshold-bump requires non-negative bump for {name}")
        bumps.append({"feature": name, "min": min_value, "max": max_value, "bump": bump_value})
    return bumps


def _build_gate_mask(
    features_frame: pd.DataFrame,
    gate_specs: list[dict[str, float | str | None]],
) -> np.ndarray:
    if not gate_specs:
        return np.ones(len(features_frame), dtype=bool)

    mask = np.ones(len(features_frame), dtype=bool)
    for gate in gate_specs:
        feature_name = str(gate["feature"])
        if feature_name not in features_frame.columns:
            raise ValueError(f"Unknown gate feature: {feature_name}")
        values = features_frame[feature_name].to_numpy(dtype=np.float64, copy=False)
        min_value = gate["min"]
        max_value = gate["max"]
        if min_value is not None:
            mask &= values >= float(min_value)
        if max_value is not None:
            mask &= values <= float(max_value)
    return mask


def _build_threshold_bump_array(
    features_frame: pd.DataFrame,
    bump_specs: list[dict[str, float | str | None]],
) -> np.ndarray:
    bumps = np.zeros(len(features_frame), dtype=np.float32)
    if not bump_specs:
        return bumps
    for bump_spec in bump_specs:
        mask = _build_gate_mask(
            features_frame,
            [
                {
                    "feature": bump_spec["feature"],
                    "min": bump_spec["min"],
                    "max": bump_spec["max"],
                }
            ],
        )
        bumps[mask] += float(bump_spec["bump"])
    return bumps


def _apply_feature_gates(
    features_frame: pd.DataFrame,
    closes: pd.Series,
    timestamps: list[object],
    gate_specs: list[dict[str, float | str | None]],
) -> tuple[pd.DataFrame, pd.Series, list[object]]:
    if not gate_specs:
        return features_frame, closes, timestamps

    mask = _build_gate_mask(features_frame, gate_specs)
    filtered_features = features_frame.loc[mask].reset_index(drop=True)
    filtered_closes = closes.loc[mask].reset_index(drop=True)
    filtered_timestamps = [ts for ts, keep in zip(timestamps, mask) if keep]
    if filtered_features.empty:
        raise ValueError("Feature gates removed all rows")
    return filtered_features, filtered_closes, filtered_timestamps


def _future_path_excursions(closes: np.ndarray, idx: int, horizon: int) -> tuple[float, float]:
    current = float(closes[idx])
    if current <= 0.0:
        return 0.0, 0.0
    end = min(len(closes), idx + max(1, int(horizon)) + 1)
    if idx + 1 >= end:
        return 0.0, 0.0
    future = np.asarray(closes[idx + 1 : end], dtype=np.float64)
    upside = max(0.0, float(np.max(future) / current - 1.0))
    downside = max(0.0, float(1.0 - np.min(future) / current))
    return upside, downside


def _load_dataset(
    *,
    data_path: str,
    env_config_path: str,
    session_filter: str,
    feature_subset_path: str,
    feature_gate_specs: list[dict[str, float | str | None]],
    action_gate_specs: list[dict[str, float | str | None]],
    threshold_bump_specs: list[dict[str, float | str | None]],
    transaction_cost_bps: float,
    slippage_bps: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[object], TradingConfig]:
    df = load_csv(data_path)
    features_frame, closes, timestamps = build_feature_frame(df)
    features_frame, closes, timestamps = filter_feature_rows_by_session(
        features_frame,
        closes,
        timestamps,
        session_filter,
    )
    features_frame, closes, timestamps = _apply_feature_gates(
        features_frame,
        closes,
        timestamps,
        feature_gate_specs,
    )
    action_gate_mask = _build_gate_mask(features_frame, action_gate_specs)
    threshold_bumps = _build_threshold_bump_array(features_frame, threshold_bump_specs)
    subset_path = str(feature_subset_path).strip()
    if subset_path:
        subset_payload = json.loads(Path(subset_path).expanduser().read_text(encoding="utf-8"))
        subset_names = subset_payload.get("selected_features", []) if isinstance(subset_payload, dict) else subset_payload
        features_frame = select_feature_columns(features_frame, subset_names)
    config = TradingConfig(
        transaction_cost_bps=transaction_cost_bps,
        slippage_bps=slippage_bps,
        episode_length=None,
        random_start=False,
    )
    if env_config_path.strip():
        loaded = load_trading_config(env_config_path)
        loaded.transaction_cost_bps = float(transaction_cost_bps)
        loaded.slippage_bps = float(slippage_bps)
        loaded.episode_length = None
        loaded.random_start = False
        config = loaded
    return (
        features_frame.to_numpy(dtype=np.float32),
        closes.to_numpy(dtype=np.float32),
        action_gate_mask.astype(bool, copy=False),
        threshold_bumps.astype(np.float32, copy=False),
        list(timestamps),
        config,
    )


def _build_targets(
    closes: np.ndarray,
    horizon: int,
    threshold: float,
    *,
    target_mode: str = "forward_return",
    follow_through_ratio: float = 1.25,
) -> tuple[np.ndarray, np.ndarray]:
    horizon = max(1, int(horizon))
    threshold = max(0.0, float(threshold))
    mode = str(target_mode).strip().lower() or "forward_return"
    if mode not in {"forward_return", "breakout_follow_through"}:
        raise ValueError(f"Unknown target mode: {target_mode}")
    ratio = max(1.0, float(follow_through_ratio))
    future_returns = np.zeros(len(closes), dtype=np.float32)
    labels = np.zeros(len(closes), dtype=np.int32)
    for idx in range(len(closes)):
        ret = compute_horizon_return(closes, idx, horizon)
        future_returns[idx] = float(ret)
        if mode == "forward_return":
            if ret > threshold:
                labels[idx] = 1
            elif ret < -threshold:
                labels[idx] = -1
            continue
        upside_exc, downside_exc = _future_path_excursions(closes, idx, horizon)
        if ret > 0.0 and upside_exc >= threshold and upside_exc >= ratio * downside_exc:
            labels[idx] = 1
        elif ret < 0.0 and downside_exc >= threshold and downside_exc >= ratio * upside_exc:
            labels[idx] = -1
    return labels, future_returns


def _fit_linear_model(train_x: np.ndarray, train_y: np.ndarray, ridge_alpha: float) -> np.ndarray | None:
    mask = train_y != 0
    if int(np.sum(mask)) < 200:
        return None
    x = train_x[mask].astype(np.float64, copy=False)
    y = train_y[mask].astype(np.float64, copy=False)
    if len(np.unique(np.sign(y))) < 2:
        return None
    ones = np.ones((x.shape[0], 1), dtype=np.float64)
    design = np.concatenate([x, ones], axis=1)
    gram = design.T @ design
    ridge = float(max(ridge_alpha, 0.0)) * np.eye(gram.shape[0], dtype=np.float64)
    ridge[-1, -1] = 0.0
    try:
        weights = np.linalg.solve(gram + ridge, design.T @ y)
    except np.linalg.LinAlgError:
        return None
    return weights.astype(np.float32, copy=False)


def _classify_position_change(old_position: float, new_position: float, eps: float = 1e-6) -> str:
    old_abs = abs(float(old_position))
    new_abs = abs(float(new_position))
    if abs(float(new_position) - float(old_position)) <= eps:
        return "none"
    if old_abs <= eps and new_abs > eps:
        return "open"
    if old_abs > eps and new_abs <= eps:
        return "close"
    if np.sign(old_position) != np.sign(new_position):
        return "reversal"
    return "resize"


def _score_to_raw_target(
    score: float,
    *,
    current_position: float,
    long_threshold: float,
    short_threshold: float,
    long_exit_threshold: float,
    short_exit_threshold: float,
    max_position: float,
    eps: float = 1e-6,
) -> float:
    max_position = float(max_position)
    current_position = float(current_position)
    if abs(current_position) <= eps:
        if score >= long_threshold:
            return max_position
        if score <= short_threshold:
            return -max_position
        return 0.0
    if current_position > 0.0:
        if score <= short_threshold:
            return -max_position
        if score <= long_exit_threshold:
            return 0.0
        return max_position
    if score >= long_threshold:
        return max_position
    if score >= short_exit_threshold:
        return 0.0
    return -max_position


def _apply_action_gate(
    raw_target: float,
    *,
    current_position: float,
    gate_enabled: bool,
    action_gate_mode: str,
    eps: float = 1e-6,
) -> float:
    if gate_enabled:
        return float(raw_target)

    mode = str(action_gate_mode).strip().lower() or "force_flat"
    if mode == "force_flat":
        return 0.0
    if mode != "entry_only":
        raise ValueError(f"Unknown action gate mode: {action_gate_mode}")

    if abs(float(current_position)) <= eps:
        return 0.0
    if np.sign(raw_target) == np.sign(current_position) and abs(float(raw_target)) > eps:
        return float(current_position)
    return 0.0


def _run_segment(
    *,
    features: np.ndarray,
    closes: np.ndarray,
    action_gate_mask: np.ndarray,
    threshold_bumps: np.ndarray,
    action_gate_mode: str,
    timestamps: list[object],
    config: TradingConfig,
    train_end: int,
    test_steps: int,
    horizon: int,
    target_threshold: float,
    target_mode: str,
    follow_through_ratio: float,
    long_threshold: float,
    short_threshold: float,
    long_exit_threshold: float,
    short_exit_threshold: float,
    ridge_alpha: float,
) -> PlaybackResult | None:
    if train_end <= 500 or train_end >= len(features) - 2:
        return None
    test_start = train_end
    test_end = min(len(features) - 1, test_start + max(1, int(test_steps)))
    if test_end - test_start <= 1:
        return None

    labels, _future_returns = _build_targets(
        closes,
        horizon,
        target_threshold,
        target_mode=target_mode,
        follow_through_ratio=follow_through_ratio,
    )
    train_frame = pd.DataFrame(features[:train_end])
    test_frame = pd.DataFrame(features[test_start:test_end])
    scaler = fit_scaler(train_frame)
    train_x = apply_scaler(train_frame, scaler).to_numpy(dtype=np.float32)
    test_x = apply_scaler(test_frame, scaler).to_numpy(dtype=np.float32)
    weights = _fit_linear_model(train_x, labels[:train_end], ridge_alpha)
    if weights is None:
        return None

    position = 0.0
    equity = 1.0
    peak_equity = 1.0
    trades = 0
    last_trade_price = None
    last_change_idx = 0
    trade_pnls: list[float] = []
    trade_costs: list[float] = []
    holding_steps: list[int] = []
    equity_series = [equity]
    max_drawdown = 0.0
    drawdown_peak_step = 0
    drawdown_trough_step = 0
    drawdown_peak_equity = equity
    drawdown_trough_equity = equity
    peak_step = 0
    action_sum = 0.0
    action_abs_sum = 0.0
    action_long = 0
    action_short = 0
    action_flat = 0
    opens = 0
    closes_count = 0
    reversals = 0
    resizes = 0
    terminal_closes = 0

    scores = (test_x @ weights[:-1]) + weights[-1]
    last_idx = -1
    for offset, idx in enumerate(range(test_start, test_end)):
        last_idx = idx
        step_num = offset + 1
        score = float(scores[offset])
        gate_enabled = bool(action_gate_mask[idx]) if len(action_gate_mask) > idx else True
        threshold_bump = float(threshold_bumps[idx]) if len(threshold_bumps) > idx else 0.0
        raw_target = _score_to_raw_target(
            score,
            current_position=position,
            long_threshold=long_threshold + threshold_bump,
            short_threshold=short_threshold - threshold_bump,
            long_exit_threshold=long_exit_threshold,
            short_exit_threshold=short_exit_threshold,
            max_position=float(config.max_position),
        )
        raw_target = _apply_action_gate(
            raw_target,
            current_position=position,
            gate_enabled=gate_enabled,
            action_gate_mode=action_gate_mode,
        )
        target_position, _ = apply_risk_engine(
            raw_target,
            current_position=position,
            config=config,
            closes=closes,
            idx=idx,
            equity=equity,
            peak_equity=peak_equity,
        )
        action_sum += target_position
        action_abs_sum += abs(target_position)
        if target_position > 0.05:
            action_long += 1
        elif target_position < -0.05:
            action_short += 1
        else:
            action_flat += 1
        delta = target_position - position
        if abs(delta) > 1e-6:
            change_kind = _classify_position_change(position, target_position)
            if change_kind == "open":
                opens += 1
            elif change_kind == "close":
                closes_count += 1
            elif change_kind == "reversal":
                reversals += 1
            elif change_kind == "resize":
                resizes += 1
            trades += 1
            holding_steps.append(step_num - 1 - last_change_idx)
            last_change_idx = step_num - 1
        transition = simulate_step_transition(
            current_position=position,
            target_position=target_position,
            closes=closes,
            idx=idx,
            equity=equity,
            peak_equity=peak_equity,
            config=config,
        )
        realized_price_return = compute_one_bar_return(closes, idx)
        realized_step_pnl = float(position) * float(realized_price_return)
        realized_net_return = realized_step_pnl - float(transition["cost"]) - float(transition["holding_cost"])
        growth_factor = max(1e-12, 1.0 + realized_net_return)
        if abs(delta) > 1e-6:
            current_price = closes[idx]
            if last_trade_price is not None:
                trade_pnl = position * (current_price - last_trade_price) / last_trade_price
                trade_pnls.append(float(trade_pnl))
                trade_costs.append(float(transition["cost"]))
            last_trade_price = current_price
        equity *= growth_factor
        if equity >= peak_equity:
            peak_step = step_num
        peak_equity = max(peak_equity, equity)
        current_drawdown = float(compute_drawdown(equity, peak_equity))
        if current_drawdown >= max_drawdown:
            max_drawdown = current_drawdown
            drawdown_peak_step = peak_step
            drawdown_trough_step = step_num
            drawdown_peak_equity = peak_equity
            drawdown_trough_equity = equity
        equity_series.append(equity)
        position = target_position

    processed_steps = max(0, last_idx - test_start + 1)
    if processed_steps <= 0:
        return None
    if abs(position) > 1e-6:
        terminal_closes += 1
    if processed_steps > last_change_idx:
        holding_steps.append(processed_steps - last_change_idx)
    total_return = equity - 1.0
    sharpe = compute_sharpe_ratio_from_equity(equity_series)
    action_avg = action_sum / processed_steps if processed_steps > 0 else 0.0
    action_abs_avg = action_abs_sum / processed_steps if processed_steps > 0 else 0.0
    total_actions = action_long + action_short + action_flat
    long_ratio = action_long / total_actions if total_actions else 0.0
    short_ratio = action_short / total_actions if total_actions else 0.0
    flat_ratio = action_flat / total_actions if total_actions else 1.0
    trade_rate_1k = (trades * 1000.0 / processed_steps) if processed_steps > 0 else 0.0
    ls_imbalance = abs(long_ratio - short_ratio)
    gate_reasons: list[str] = []
    if total_return <= 0.0:
        gate_reasons.append("non-positive return")
    if max_drawdown > 0.15:
        gate_reasons.append("drawdown > 15%")
    if sharpe < 0.003:
        gate_reasons.append("sharpe < 0.003")
    if trade_rate_1k < 5.0:
        gate_reasons.append("trade rate < 5/1k")
    if trade_rate_1k > 120.0:
        gate_reasons.append("trade rate > 120/1k")
    if flat_ratio > 0.90:
        gate_reasons.append("flat ratio > 0.90")
    if ls_imbalance > 0.35:
        gate_reasons.append("|long-short| > 0.35")
    end_index = test_start + processed_steps
    return PlaybackResult(
        start_index=test_start,
        end_index=end_index,
        processed_steps=processed_steps,
        trades=trades,
        equity=equity,
        total_return=total_return,
        sharpe=sharpe,
        max_drawdown=max_drawdown,
        trade_pnls=trade_pnls,
        trade_costs=trade_costs,
        holding_steps=holding_steps,
        opens=opens,
        closes=closes_count,
        reversals=reversals,
        resizes=resizes,
        terminal_closes=terminal_closes,
        action_avg=action_avg,
        action_abs_avg=action_abs_avg,
        long_ratio=long_ratio,
        short_ratio=short_ratio,
        flat_ratio=flat_ratio,
        trade_rate_1k=trade_rate_1k,
        ls_imbalance=ls_imbalance,
        start_ts=timestamps[test_start],
        end_ts=timestamps[end_index] if end_index < len(timestamps) else timestamps[-1],
        drawdown_peak_step=drawdown_peak_step,
        drawdown_trough_step=drawdown_trough_step,
        drawdown_peak_equity=drawdown_peak_equity,
        drawdown_trough_equity=drawdown_trough_equity,
        gate_reasons=gate_reasons,
    )


def _aggregate(results: list[PlaybackResult]) -> dict[str, float]:
    if not results:
        return {
            "segments": 0.0,
            "pass_count": 0.0,
            "pass_rate": 0.0,
            "avg_return": 0.0,
            "avg_sharpe": 0.0,
            "avg_max_drawdown": 0.0,
            "avg_trade_rate_1k": 0.0,
        }
    returns = np.asarray([r.total_return for r in results], dtype=np.float64)
    sharpes = np.asarray([r.sharpe for r in results], dtype=np.float64)
    drawdowns = np.asarray([r.max_drawdown for r in results], dtype=np.float64)
    trade_rates = np.asarray([r.trade_rate_1k for r in results], dtype=np.float64)
    pass_count = sum(1 for r in results if not r.gate_reasons)
    return {
        "segments": float(len(results)),
        "pass_count": float(pass_count),
        "pass_rate": float(pass_count / len(results)),
        "avg_return": float(np.mean(returns)),
        "avg_sharpe": float(np.mean(sharpes)),
        "avg_max_drawdown": float(np.mean(drawdowns)),
        "avg_trade_rate_1k": float(np.mean(trade_rates)),
    }


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Walk-forward logistic-regression baseline on RL features.")
    parser.add_argument("--data", required=True, help="Path to raw history CSV.")
    parser.add_argument("--env-config", default="", help="Optional env config JSON.")
    parser.add_argument(
        "--session-filter",
        choices=("all", "monday_open", "london", "london_pre_ny", "ny", "overlap"),
        default="all",
        help="Session filter applied before training and evaluation.",
    )
    parser.add_argument(
        "--feature-subset-json",
        default="",
        help="Optional JSON file containing selected_features for feature ablation.",
    )
    parser.add_argument(
        "--feature-gate",
        action="append",
        default=[],
        help="Optional row filter in feature:min:max format. May be repeated.",
    )
    parser.add_argument(
        "--action-gate",
        action="append",
        default=[],
        help="Optional execution gate in feature:min:max format. May be repeated.",
    )
    parser.add_argument(
        "--action-gate-mode",
        choices=("force_flat", "entry_only"),
        default="force_flat",
        help="How action gates affect positions when the gate is closed.",
    )
    parser.add_argument(
        "--threshold-bump",
        action="append",
        default=[],
        help="Optional regime-conditioned threshold bump in feature:min:max:bump format. May be repeated.",
    )
    parser.add_argument("--transaction-cost-bps", type=float, default=1.0)
    parser.add_argument("--slippage-bps", type=float, default=0.5)
    parser.add_argument("--horizon", type=int, default=20, help="Forward-return label horizon in bars.")
    parser.add_argument("--target-threshold", type=float, default=0.0, help="Dead-zone threshold for labels.")
    parser.add_argument(
        "--target-mode",
        choices=("forward_return", "breakout_follow_through"),
        default="forward_return",
        help="Label definition for supervised targets.",
    )
    parser.add_argument(
        "--follow-through-ratio",
        type=float,
        default=1.25,
        help="Directional dominance ratio for breakout_follow_through targets.",
    )
    parser.add_argument("--long-threshold", type=float, default=0.15, help="Score threshold for long.")
    parser.add_argument("--short-threshold", type=float, default=-0.15, help="Score threshold for short.")
    parser.add_argument(
        "--long-exit-threshold",
        type=float,
        default=None,
        help="Optional long exit threshold. Defaults to --long-threshold.",
    )
    parser.add_argument(
        "--short-exit-threshold",
        type=float,
        default=None,
        help="Optional short exit threshold. Defaults to --short-threshold.",
    )
    parser.add_argument("--ridge-alpha", type=float, default=1.0, help="L2 regularization strength for linear model.")
    parser.add_argument("--segments", type=int, default=6, help="Number of walk-forward segments.")
    parser.add_argument("--test-steps", type=int, default=10000, help="Steps per walk-forward test segment.")
    parser.add_argument("--stride", type=int, default=20000, help="Stride between successive train/test boundaries.")
    parser.add_argument("--train-min-rows", type=int, default=20000, help="Minimum train rows before first test segment.")
    parser.add_argument("--json-out", default="", help="Optional JSON output path.")
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()
    if args.short_threshold >= args.long_threshold:
        raise ValueError("--short-threshold must be < --long-threshold")
    long_exit_threshold = (
        float(args.long_threshold) if args.long_exit_threshold is None else float(args.long_exit_threshold)
    )
    short_exit_threshold = (
        float(args.short_threshold) if args.short_exit_threshold is None else float(args.short_exit_threshold)
    )
    if long_exit_threshold > float(args.long_threshold):
        raise ValueError("--long-exit-threshold must be <= --long-threshold")
    if short_exit_threshold < float(args.short_threshold):
        raise ValueError("--short-exit-threshold must be >= --short-threshold")
    if short_exit_threshold >= long_exit_threshold:
        raise ValueError("--short-exit-threshold must be < --long-exit-threshold")
    gate_specs = _parse_feature_gate_specs(list(args.feature_gate))
    action_gate_specs = _parse_action_gate_specs(list(args.action_gate))
    threshold_bump_specs = _parse_threshold_bump_specs(list(args.threshold_bump))

    features, closes, action_gate_mask, threshold_bumps, timestamps, config = _load_dataset(
        data_path=args.data,
        env_config_path=args.env_config,
        session_filter=args.session_filter,
        feature_subset_path=args.feature_subset_json,
        feature_gate_specs=gate_specs,
        action_gate_specs=action_gate_specs,
        threshold_bump_specs=threshold_bump_specs,
        transaction_cost_bps=float(args.transaction_cost_bps),
        slippage_bps=float(args.slippage_bps),
    )
    results: list[PlaybackResult] = []
    for segment_idx in range(int(args.segments)):
        train_end = int(args.train_min_rows) + segment_idx * int(args.stride)
        result = _run_segment(
            features=features,
            closes=closes,
            action_gate_mask=action_gate_mask,
            threshold_bumps=threshold_bumps,
            action_gate_mode=str(args.action_gate_mode),
            timestamps=timestamps,
            config=config,
            train_end=train_end,
            test_steps=int(args.test_steps),
            horizon=int(args.horizon),
            target_threshold=float(args.target_threshold),
            target_mode=str(args.target_mode),
            follow_through_ratio=float(args.follow_through_ratio),
            long_threshold=float(args.long_threshold),
            short_threshold=float(args.short_threshold),
            long_exit_threshold=long_exit_threshold,
            short_exit_threshold=short_exit_threshold,
            ridge_alpha=float(args.ridge_alpha),
        )
        if result is None:
            break
        print(f"\nSegment {segment_idx + 1} train_end={train_end}")
        print_playback_result(result)
        results.append(result)

    aggregate = _aggregate(results)
    print(
        "\nAggregate:",
        f"segments={int(aggregate['segments'])}",
        f"pass={int(aggregate['pass_count'])}",
        f"avg_return={aggregate['avg_return']:.6f}",
        f"avg_sharpe={aggregate['avg_sharpe']:.6f}",
        f"avg_max_dd={aggregate['avg_max_drawdown']:.6f}",
        f"avg_trade_rate/1k={aggregate['avg_trade_rate_1k']:.2f}",
    )
    if args.json_out.strip():
        payload = {
            "session_filter": args.session_filter,
            "feature_subset_json": str(args.feature_subset_json).strip(),
            "feature_gates": gate_specs,
            "action_gates": action_gate_specs,
            "action_gate_mode": str(args.action_gate_mode),
            "threshold_bumps": threshold_bump_specs,
            "horizon": int(args.horizon),
            "target_threshold": float(args.target_threshold),
            "target_mode": str(args.target_mode),
            "follow_through_ratio": float(args.follow_through_ratio),
            "long_threshold": float(args.long_threshold),
            "short_threshold": float(args.short_threshold),
            "long_exit_threshold": long_exit_threshold,
            "short_exit_threshold": short_exit_threshold,
            "ridge_alpha": float(args.ridge_alpha),
            "aggregate": aggregate,
            "segments": [
                {
                    "start_index": result.start_index,
                    "end_index": result.end_index,
                    "start_ts": str(result.start_ts),
                    "end_ts": str(result.end_ts),
                    "total_return": float(result.total_return),
                    "sharpe": float(result.sharpe),
                    "max_drawdown": float(result.max_drawdown),
                    "trade_rate_1k": float(result.trade_rate_1k),
                    "ls_imbalance": float(result.ls_imbalance),
                    "flat_ratio": float(result.flat_ratio),
                    "gate_reasons": list(result.gate_reasons),
                }
                for result in results
            ],
        }
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
