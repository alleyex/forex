from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from forex.ml.rl.envs.trading_config_io import load_trading_config
from forex.ml.rl.envs.trading_env import TradingConfig, apply_risk_engine, simulate_step_transition
from forex.ml.rl.features.feature_builder import build_feature_frame, load_csv
from forex.ml.rl.features.feature_builder import filter_feature_rows_by_session
from forex.tools.rl.run_live_sim import PlaybackResult, print_playback_result
from forex.utils.metrics import compute_sharpe_ratio_from_equity


@dataclass(frozen=True)
class BaselineBundle:
    features: pd.DataFrame
    closes: np.ndarray
    timestamps: list[object]
    config: TradingConfig


def load_baseline_bundle(
    *,
    data_path: str,
    env_config_path: str = "",
    transaction_cost_bps: float = 1.0,
    slippage_bps: float = 0.5,
) -> BaselineBundle:
    df = load_csv(data_path)
    features_frame, closes, timestamps = build_feature_frame(df)
    features_frame, closes, timestamps = filter_feature_rows_by_session(
        features_frame,
        closes,
        timestamps,
        "all",
    )
    config = TradingConfig(
        transaction_cost_bps=transaction_cost_bps,
        slippage_bps=slippage_bps,
        episode_length=None,
        random_start=False,
    )
    if env_config_path.strip():
        try:
            loaded = load_trading_config(env_config_path)
            loaded.transaction_cost_bps = float(transaction_cost_bps)
            loaded.slippage_bps = float(slippage_bps)
            loaded.episode_length = None
            loaded.random_start = False
            config = loaded
        except Exception:
            pass
    return BaselineBundle(
        features=features_frame,
        closes=closes.to_numpy(dtype=np.float32),
        timestamps=list(timestamps),
        config=config,
    )


def _fixed_position(value: float):
    def _fn(_features: pd.DataFrame, _idx: int, config: TradingConfig) -> float:
        return float(np.clip(value, -config.max_position, config.max_position))

    return _fn


def _momentum_fn(features: pd.DataFrame, idx: int, config: TradingConfig) -> float:
    row = features.iloc[idx]
    if float(row["adx_14"]) < 20.0:
        return 0.0
    if float(row["momentum_10_20"]) > 0.0 and float(row["momentum_20_50"]) > 0.0:
        return float(config.max_position)
    if float(row["momentum_10_20"]) < 0.0 and float(row["momentum_20_50"]) < 0.0:
        return float(-config.max_position)
    return 0.0


def _breakout20_fn(features: pd.DataFrame, idx: int, config: TradingConfig) -> float:
    row = features.iloc[idx]
    if float(row["adx_14"]) < 20.0:
        return 0.0
    if float(row["breakout_20"]) > 0.0:
        return float(config.max_position)
    if float(row["distance_to_rolling_low_20"]) < 0.0:
        return float(-config.max_position)
    return 0.0


def _breakout50_fn(features: pd.DataFrame, idx: int, config: TradingConfig) -> float:
    row = features.iloc[idx]
    if float(row["adx_14"]) < 20.0:
        return 0.0
    if float(row["breakout_50"]) > 0.0:
        return float(config.max_position)
    if float(row["momentum_20_50"]) < 0.0 and float(row["returns_20"]) < 0.0:
        return float(-config.max_position)
    return 0.0


def _mean_revert_fn(features: pd.DataFrame, idx: int, config: TradingConfig) -> float:
    row = features.iloc[idx]
    z = float(row["price_z_20"])
    if z > 1.0:
        return float(-config.max_position)
    if z < -1.0:
        return float(config.max_position)
    return 0.0


def _short_bias_fn(features: pd.DataFrame, idx: int, config: TradingConfig) -> float:
    row = features.iloc[idx]
    if float(row["momentum_20_50"]) < 0.0 and float(row["adx_14"]) >= 18.0:
        return float(-config.max_position)
    return 0.0


def _regime_switch_fn(features: pd.DataFrame, idx: int, config: TradingConfig) -> float:
    row = features.iloc[idx]
    adx = float(row["adx_14"])
    momentum_fast = float(row["momentum_10_20"])
    momentum_slow = float(row["momentum_20_50"])
    ret_20 = float(row["returns_20"])
    z20 = float(row["price_z_20"])
    if adx >= 22.0:
        if momentum_fast > 0.0 and momentum_slow > 0.0 and ret_20 > 0.0:
            return float(config.max_position)
        if momentum_fast < 0.0 and momentum_slow < 0.0 and ret_20 < 0.0:
            return float(-config.max_position)
        return 0.0
    if z20 > 1.0:
        return float(-0.5 * config.max_position)
    if z20 < -1.0:
        return float(0.5 * config.max_position)
    return 0.0


def _regime_short_mr_fn(features: pd.DataFrame, idx: int, config: TradingConfig) -> float:
    row = features.iloc[idx]
    adx = float(row["adx_14"])
    momentum_slow = float(row["momentum_20_50"])
    ret_20 = float(row["returns_20"])
    z20 = float(row["price_z_20"])
    if adx >= 18.0 and momentum_slow < 0.0 and ret_20 < 0.0:
        return float(-config.max_position)
    if adx < 18.0:
        if z20 > 1.0:
            return float(-0.5 * config.max_position)
        if z20 < -1.0:
            return float(0.5 * config.max_position)
    return 0.0


BASELINES = {
    "flat": _fixed_position(0.0),
    "long": _fixed_position(1.0),
    "short": _fixed_position(-1.0),
    "momentum": _momentum_fn,
    "breakout20": _breakout20_fn,
    "breakout50": _breakout50_fn,
    "mean_revert": _mean_revert_fn,
    "short_bias": _short_bias_fn,
    "regime_switch": _regime_switch_fn,
    "regime_short_mr": _regime_short_mr_fn,
}

SESSION_FILTERS = {
    "all": None,
    "monday_open": "is_monday_open_window",
    "london": "is_london_session",
    "london_pre_ny": "is_london_pre_ny_session",
    "ny": "is_ny_session",
    "overlap": "is_london_ny_overlap",
}


def _session_allows(features: pd.DataFrame, idx: int, session_name: str) -> bool:
    column = SESSION_FILTERS.get(session_name)
    if column is None:
        return True
    return float(features.iloc[idx][column]) > 0.5


def _result_to_dict(result: PlaybackResult) -> dict[str, object]:
    return {
        "start_index": result.start_index,
        "end_index": result.end_index,
        "start_ts": str(result.start_ts),
        "end_ts": str(result.end_ts),
        "processed_steps": result.processed_steps,
        "trades": result.trades,
        "equity": float(result.equity),
        "total_return": float(result.total_return),
        "sharpe": float(result.sharpe),
        "max_drawdown": float(result.max_drawdown),
        "trade_rate_1k": float(result.trade_rate_1k),
        "long_ratio": float(result.long_ratio),
        "short_ratio": float(result.short_ratio),
        "flat_ratio": float(result.flat_ratio),
        "long_short_imbalance": float(result.ls_imbalance),
        "gate_pass": not result.gate_reasons,
        "gate_reasons": list(result.gate_reasons),
    }


def _aggregate_results(results: list[PlaybackResult]) -> dict[str, object]:
    if not results:
        return {
            "segments": 0,
            "pass_count": 0,
            "pass_rate": 0.0,
            "avg_return": 0.0,
            "avg_sharpe": 0.0,
            "avg_max_drawdown": 0.0,
            "worst_max_drawdown": 0.0,
            "avg_trade_rate_1k": 0.0,
        }
    returns = np.asarray([result.total_return for result in results], dtype=np.float64)
    sharpes = np.asarray([result.sharpe for result in results], dtype=np.float64)
    drawdowns = np.asarray([result.max_drawdown for result in results], dtype=np.float64)
    trade_rates = np.asarray([result.trade_rate_1k for result in results], dtype=np.float64)
    pass_count = sum(1 for result in results if not result.gate_reasons)
    return {
        "segments": len(results),
        "pass_count": int(pass_count),
        "pass_rate": float(pass_count / len(results)),
        "avg_return": float(np.mean(returns)),
        "avg_sharpe": float(np.mean(sharpes)),
        "avg_max_drawdown": float(np.mean(drawdowns)),
        "worst_max_drawdown": float(np.max(drawdowns)),
        "avg_trade_rate_1k": float(np.mean(trade_rates)),
    }


def run_heuristic_playback(
    bundle: BaselineBundle,
    strategy_name: str,
    *,
    session_name: str = "all",
    start_index: int = 0,
    max_steps: int = 0,
) -> PlaybackResult:
    signal_fn = BASELINES[strategy_name]
    start_idx = max(0, int(start_index))
    last_feature_idx = len(bundle.features) - 1
    if start_idx >= last_feature_idx:
        raise ValueError("Start index is beyond the available playback range.")
    available_steps = last_feature_idx - start_idx
    step_limit = available_steps if max_steps <= 0 else min(available_steps, int(max_steps))
    if step_limit <= 0:
        raise ValueError("Not enough rows after feature building.")

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
    action_sum = 0.0
    action_long = 0
    action_short = 0
    action_flat = 0
    last_idx = -1

    for idx in range(start_idx, start_idx + step_limit):
        last_idx = idx
        step_num = idx - start_idx + 1
        raw_target = 0.0
        if _session_allows(bundle.features, idx, session_name):
            raw_target = signal_fn(bundle.features, idx, bundle.config)
        target_position, _risk_info = apply_risk_engine(
            raw_target,
            current_position=position,
            config=bundle.config,
            closes=bundle.closes,
            idx=idx,
            equity=equity,
            peak_equity=peak_equity,
        )
        action_sum += target_position
        if target_position > 0.05:
            action_long += 1
        elif target_position < -0.05:
            action_short += 1
        else:
            action_flat += 1
        delta = target_position - position
        if abs(delta) > 1e-6:
            trades += 1
            holding_steps.append(step_num - 1 - last_change_idx)
            last_change_idx = step_num - 1
        transition = simulate_step_transition(
            current_position=position,
            target_position=target_position,
            closes=bundle.closes,
            idx=idx,
            equity=equity,
            peak_equity=peak_equity,
            config=bundle.config,
        )
        if abs(delta) > 1e-6:
            current_price = bundle.closes[idx]
            if last_trade_price is not None:
                trade_pnl = position * (current_price - last_trade_price) / last_trade_price
                trade_pnls.append(float(trade_pnl))
                trade_costs.append(float(transition["cost"]))
            last_trade_price = current_price
        equity = transition["equity"]
        peak_equity = transition["peak_equity"]
        max_drawdown = max(max_drawdown, float(transition["drawdown"]))
        equity_series.append(equity)
        position = target_position

    processed_steps = max(0, last_idx - start_idx + 1)
    if processed_steps > last_change_idx:
        holding_steps.append(processed_steps - last_change_idx)
    total_return = equity - 1.0
    sharpe = compute_sharpe_ratio_from_equity(equity_series)
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
    end_index = start_idx + processed_steps
    start_ts = bundle.timestamps[start_idx] if start_idx < len(bundle.timestamps) else "-"
    end_ts = bundle.timestamps[end_index] if end_index < len(bundle.timestamps) else "-"
    return PlaybackResult(
        start_index=start_idx,
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
        action_avg=(action_sum / processed_steps) if processed_steps > 0 else 0.0,
        long_ratio=long_ratio,
        short_ratio=short_ratio,
        flat_ratio=flat_ratio,
        trade_rate_1k=trade_rate_1k,
        ls_imbalance=ls_imbalance,
        start_ts=start_ts,
        end_ts=end_ts,
        gate_reasons=gate_reasons,
    )


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate simple non-RL trading baselines on the same playback stack.")
    parser.add_argument("--data", required=True, help="Path to raw history CSV.")
    parser.add_argument("--env-config", default="", help="Optional env config JSON.")
    parser.add_argument("--transaction-cost-bps", type=float, default=1.0, help="Transaction cost in bps.")
    parser.add_argument("--slippage-bps", type=float, default=0.5, help="Slippage in bps.")
    parser.add_argument("--start-index", type=int, default=0, help="Zero-based bar index to start playback from.")
    parser.add_argument("--max-steps", type=int, default=10000, help="Playback steps per strategy (0 = full length).")
    parser.add_argument("--segments", type=int, default=1, help="Number of walk-forward segments to evaluate.")
    parser.add_argument("--stride", type=int, default=5000, help="Start-index stride between segments.")
    parser.add_argument(
        "--strategies",
        default="momentum,breakout20,breakout50,mean_revert,short_bias,regime_switch,regime_short_mr,long,short,flat",
        help="Comma-separated baseline strategy names.",
    )
    parser.add_argument(
        "--sessions",
        default="all",
        help="Comma-separated session filters: all,monday_open,london,london_pre_ny,ny,overlap.",
    )
    parser.add_argument("--json-out", default="", help="Optional JSON path to save summary rows.")
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()
    bundle = load_baseline_bundle(
        data_path=args.data,
        env_config_path=args.env_config,
        transaction_cost_bps=args.transaction_cost_bps,
        slippage_bps=args.slippage_bps,
    )
    strategies = [item.strip() for item in str(args.strategies).split(",") if item.strip()]
    unknown = [name for name in strategies if name not in BASELINES]
    if unknown:
        raise ValueError(f"Unknown strategies: {', '.join(unknown)}")
    sessions = [item.strip() for item in str(args.sessions).split(",") if item.strip()]
    unknown_sessions = [name for name in sessions if name not in SESSION_FILTERS]
    if unknown_sessions:
        raise ValueError(f"Unknown sessions: {', '.join(unknown_sessions)}")
    if int(args.segments) <= 0:
        raise ValueError("--segments must be > 0")
    if int(args.stride) <= 0:
        raise ValueError("--stride must be > 0")
    summaries: list[dict[str, object]] = []
    for session_name in sessions:
        for name in strategies:
            print(f"\nStrategy: {name} session={session_name}")
            segment_results: list[PlaybackResult] = []
            for segment_idx in range(int(args.segments)):
                current_start = int(args.start_index) + segment_idx * int(args.stride)
                try:
                    result = run_heuristic_playback(
                        bundle,
                        name,
                        session_name=session_name,
                        start_index=current_start,
                        max_steps=args.max_steps,
                    )
                except ValueError:
                    break
                segment_results.append(result)
                if int(args.segments) > 1:
                    gate_text = "PASS" if not result.gate_reasons else f"FAIL ({'; '.join(result.gate_reasons)})"
                    print(
                        f"Segment {segment_idx + 1}: range={result.start_ts} -> {result.end_ts} "
                        f"return={result.total_return:.6f} sharpe={result.sharpe:.6f} "
                        f"max_dd={result.max_drawdown:.6f} trade_rate/1k={result.trade_rate_1k:.2f} gate={gate_text}"
                    )
            if not segment_results:
                continue
            if int(args.segments) == 1:
                print_playback_result(segment_results[0])
            aggregate = _aggregate_results(segment_results)
            if int(args.segments) > 1:
                print(
                    "Aggregate: "
                    f"segments={aggregate['segments']} pass={aggregate['pass_count']} "
                    f"avg_return={aggregate['avg_return']:.6f} avg_sharpe={aggregate['avg_sharpe']:.6f} "
                    f"avg_max_dd={aggregate['avg_max_drawdown']:.6f} "
                    f"worst_max_dd={aggregate['worst_max_drawdown']:.6f} "
                    f"avg_trade_rate/1k={aggregate['avg_trade_rate_1k']:.2f}"
                )
            summaries.append(
                {
                    "strategy": name,
                    "session": session_name,
                    "aggregate": aggregate,
                    "segments": [_result_to_dict(result) for result in segment_results],
                }
            )
    if args.json_out.strip():
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(summaries, ensure_ascii=True, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
