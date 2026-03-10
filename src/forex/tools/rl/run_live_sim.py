from __future__ import annotations

import argparse
import signal
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from stable_baselines3 import PPO

from forex.config.paths import DEFAULT_MODEL_PATH
from forex.ml.rl.envs.trading_config_io import load_trading_config
from forex.ml.rl.envs.trading_env import (
    TradingConfig,
    apply_risk_engine,
    build_window_observation,
    simulate_step_transition,
)
from forex.ml.rl.features.feature_builder import (
    apply_feature_profile,
    apply_scaler,
    build_feature_frame,
    filter_feature_rows_by_session,
    infer_feature_profile_from_names,
    load_csv,
    load_scaler,
)
from forex.utils.metrics import compute_sharpe_ratio_from_equity


@dataclass
class PlaybackBundle:
    features: np.ndarray
    closes: np.ndarray
    timestamps: list[object]
    config: TradingConfig
    model: PPO


@dataclass
class SimState:
    position: float = 0.0
    equity: float = 1.0


@dataclass
class PlaybackResult:
    start_index: int
    end_index: int
    processed_steps: int
    trades: int
    equity: float
    total_return: float
    sharpe: float
    max_drawdown: float
    trade_pnls: list[float]
    trade_costs: list[float]
    holding_steps: list[int]
    opens: int
    closes: int
    reversals: int
    resizes: int
    terminal_closes: int
    action_avg: float
    action_abs_avg: float
    long_ratio: float
    short_ratio: float
    flat_ratio: float
    trade_rate_1k: float
    ls_imbalance: float
    start_ts: object
    end_ts: object
    drawdown_peak_step: int
    drawdown_trough_step: int
    drawdown_peak_equity: float
    drawdown_trough_equity: float
    gate_reasons: list[str]


def _streak_stats(values: list[float]) -> tuple[int, int]:
    max_win = 0
    max_loss = 0
    current_win = 0
    current_loss = 0
    for value in values:
        if value > 0:
            current_win += 1
            current_loss = 0
        elif value < 0:
            current_loss += 1
            current_win = 0
        else:
            current_win = 0
            current_loss = 0
        max_win = max(max_win, current_win)
        max_loss = max(max_loss, current_loss)
    return max_win, max_loss


def _split_transition_cost(old_position: float, new_position: float, cost_rate: float) -> tuple[float, float]:
    old_abs = abs(float(old_position))
    new_abs = abs(float(new_position))
    if old_abs <= 1e-12 and new_abs <= 1e-12:
        return 0.0, 0.0
    old_sign = float(np.sign(old_position))
    new_sign = float(np.sign(new_position))
    if old_abs <= 1e-12:
        return 0.0, new_abs * cost_rate
    if new_abs <= 1e-12:
        return old_abs * cost_rate, 0.0
    if old_sign == new_sign:
        if new_abs >= old_abs:
            return 0.0, (new_abs - old_abs) * cost_rate
        return (old_abs - new_abs) * cost_rate, 0.0
    return old_abs * cost_rate, new_abs * cost_rate


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


def load_playback_bundle(
    *,
    data_path: str,
    model_path: str,
    feature_scaler_path: str = "",
    env_config_path: str = "",
    session_filter: str = "all",
    transaction_cost_bps: float = 1.0,
    slippage_bps: float = 0.5,
) -> PlaybackBundle:
    df = load_csv(data_path)
    features_frame, closes, timestamps = build_feature_frame(df)
    features_frame, closes, timestamps = filter_feature_rows_by_session(
        features_frame,
        closes,
        timestamps,
        session_filter,
    )

    scaler_path = feature_scaler_path.strip()
    if not scaler_path:
        scaler_path = str(Path(model_path).with_suffix(".scaler.json"))
    scaler_file = Path(scaler_path)
    if scaler_file.exists():
        scaler = load_scaler(scaler_file)
        feature_profile = infer_feature_profile_from_names(scaler.names)
        features_frame = apply_feature_profile(features_frame, feature_profile)
        features_frame = apply_scaler(features_frame, scaler)

    config = TradingConfig(
        transaction_cost_bps=transaction_cost_bps,
        slippage_bps=slippage_bps,
        episode_length=None,
        random_start=False,
    )
    config_path = env_config_path.strip()
    if not config_path:
        config_path = str(Path(model_path).with_suffix(".env.json"))
    config_file = Path(config_path)
    if config_file.exists():
        try:
            loaded_config = load_trading_config(config_file)
            loaded_config.transaction_cost_bps = float(transaction_cost_bps)
            loaded_config.slippage_bps = float(slippage_bps)
            loaded_config.episode_length = None
            loaded_config.random_start = False
            config = loaded_config
        except Exception:
            pass

    model = PPO.load(model_path)
    model_obs_shape = getattr(getattr(model, "observation_space", None), "shape", None)
    expected_obs_dim = int(np.prod(model_obs_shape)) if model_obs_shape else 0
    window_size = max(1, int(getattr(config, "window_size", 1)))
    actual_obs_dim = (int(features_frame.shape[1]) * window_size) + 1
    if expected_obs_dim > 0 and expected_obs_dim != actual_obs_dim:
        raise ValueError(
            "Model observation dimension mismatch. "
            f"model expects {expected_obs_dim}, but data pipeline produced {actual_obs_dim}. "
            "Check feature profile/scaler/env config alignment."
        )

    return PlaybackBundle(
        features=features_frame.to_numpy(dtype=np.float32),
        closes=closes.to_numpy(dtype=np.float32),
        timestamps=list(timestamps),
        config=config,
        model=model,
    )


def simulate_fixed_position(bundle: PlaybackBundle, position: float, start_index: int, steps: int) -> tuple[float, float]:
    equity = 1.0
    peak_equity = 1.0
    current_position = 0.0
    for idx in range(start_index, start_index + steps):
        transition = simulate_step_transition(
            current_position=current_position,
            target_position=position,
            closes=bundle.closes,
            idx=idx,
            equity=equity,
            peak_equity=peak_equity,
            config=bundle.config,
        )
        equity = transition["equity"]
        peak_equity = transition["peak_equity"]
        current_position = position
    return equity, equity - 1.0


def run_playback(
    bundle: PlaybackBundle,
    *,
    start_index: int = 0,
    max_steps: int = 0,
    stochastic: bool = False,
    log_every: int = 200,
    quiet: bool = False,
    equity_log_path: str = "",
    equity_log_every: int = 200,
    should_stop: Callable[[], bool] | None = None,
) -> PlaybackResult:
    state = SimState()
    start_idx = max(0, int(start_index))
    last_feature_idx = len(bundle.features) - 1
    if start_idx >= last_feature_idx:
        raise ValueError("Start index is beyond the available playback range.")

    available_steps = last_feature_idx - start_idx
    step_limit = available_steps
    if max_steps > 0:
        step_limit = min(step_limit, int(max_steps))
    if step_limit <= 0:
        raise ValueError("Not enough rows after feature building; check data columns.")

    equity_log_file = None
    log_every_n = max(1, int(equity_log_every))
    if equity_log_path.strip():
        log_path = Path(equity_log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        equity_log_file = log_path.open("w", encoding="utf-8")
        equity_log_file.write("step,equity\n")

    peak_equity = state.equity
    peak_step = 0
    equity_series = [state.equity]
    max_drawdown = 0.0
    drawdown_peak_step = 0
    drawdown_trough_step = 0
    drawdown_peak_equity = state.equity
    drawdown_trough_equity = state.equity
    action_sum = 0.0
    action_long = 0
    action_short = 0
    action_flat = 0
    opens = 0
    closes = 0
    reversals = 0
    resizes = 0
    terminal_closes = 0
    trade_pnls: list[float] = []
    trade_costs: list[float] = []
    holding_steps: list[int] = []
    action_abs_sum = 0.0
    current_trade_growth: float | None = None
    current_trade_cost: float = 0.0
    current_trade_start_step: int | None = None
    last_idx = -1

    try:
        for idx in range(start_idx, start_idx + step_limit):
            if should_stop and should_stop():
                break

            last_idx = idx
            step_num = idx - start_idx + 1
            obs = build_window_observation(
                bundle.features,
                idx,
                position=state.position,
                max_position=bundle.config.max_position,
                window_size=getattr(bundle.config, "window_size", 1),
            )
            action, _ = bundle.model.predict(obs, deterministic=not stochastic)
            target_raw = float(np.asarray(action, dtype=np.float32).reshape(-1)[0])
            target_position, risk_info = apply_risk_engine(
                target_raw,
                current_position=state.position,
                config=bundle.config,
                closes=bundle.closes,
                idx=idx,
                equity=state.equity,
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

            delta = target_position - state.position
            if abs(delta) > 1e-6:
                change_kind = _classify_position_change(state.position, target_position)
                if change_kind == "open":
                    opens += 1
                elif change_kind == "close":
                    closes += 1
                elif change_kind == "reversal":
                    reversals += 1
                elif change_kind == "resize":
                    resizes += 1

            transition = simulate_step_transition(
                current_position=state.position,
                target_position=target_position,
                closes=bundle.closes,
                idx=idx,
                equity=state.equity,
                peak_equity=peak_equity,
                config=bundle.config,
            )
            cost_rate = (float(bundle.config.transaction_cost_bps) + float(bundle.config.slippage_bps)) / 10000.0
            exit_cost, entry_cost = _split_transition_cost(state.position, target_position, cost_rate)
            if abs(state.position) > 1e-6:
                if current_trade_growth is None:
                    current_trade_growth = 1.0
                    current_trade_cost = 0.0
                trade_bar_net = transition["step_pnl"] - exit_cost - transition["holding_cost"]
                current_trade_growth *= max(1e-12, 1.0 + float(trade_bar_net))
                current_trade_cost += float(exit_cost + transition["holding_cost"])
            if abs(delta) > 1e-6:
                execution_idx = idx + 1
                current_time = (
                    bundle.timestamps[execution_idx] if execution_idx < len(bundle.timestamps) else "-"
                )
                if change_kind == "resize" and current_trade_growth is not None:
                    current_trade_growth *= max(1e-12, 1.0 - entry_cost)
                    current_trade_cost += float(entry_cost)
                if change_kind in {"close", "reversal"} and abs(state.position) > 1e-6 and current_trade_growth is not None:
                    trade_pnl = current_trade_growth - 1.0
                    trade_pnls.append(float(trade_pnl))
                    trade_costs.append(float(current_trade_cost))
                    if current_trade_start_step is not None:
                        holding_steps.append(step_num - current_trade_start_step)
                    if not quiet:
                        print(
                            f"Trade @ {current_time} pos={state.position:.3f} -> {target_position:.3f} "
                            f"net_return={trade_pnl:.6g} cost={current_trade_cost:.6g} "
                            f"holding={transition['holding_cost']:.6g}"
                        )
                    current_trade_growth = None
                    current_trade_cost = 0.0
                    current_trade_start_step = None
                if change_kind in {"open", "reversal"} and abs(target_position) > 1e-6:
                    current_trade_growth = max(1e-12, 1.0 - entry_cost)
                    current_trade_cost = float(entry_cost)
                    current_trade_start_step = step_num

            reward = transition["reward"]
            state.equity = transition["equity"]
            equity_series.append(state.equity)
            state.position = target_position
            if state.equity >= peak_equity:
                peak_step = step_num
                drawdown_peak_equity = state.equity
            peak_equity = transition["peak_equity"]
            current_drawdown = float(transition["drawdown"])
            if current_drawdown >= max_drawdown:
                max_drawdown = current_drawdown
                drawdown_peak_step = peak_step
                drawdown_trough_step = step_num
                drawdown_peak_equity = peak_equity
                drawdown_trough_equity = state.equity

            if equity_log_file and step_num % log_every_n == 0:
                equity_log_file.write(f"{step_num},{state.equity:.6f}\n")
                if step_num % (log_every_n * 5) == 0:
                    equity_log_file.flush()
            if not quiet and log_every and step_num % log_every == 0:
                ts = bundle.timestamps[idx + 1] if idx + 1 < len(bundle.timestamps) else "-"
                print(
                    f"[{ts}] step={step_num} equity={state.equity:.6f} "
                    f"pos={state.position:.3f} reward={reward:.6g} "
                    f"vol_scale={risk_info['vol_target_scale']:.3f}"
                )
    finally:
        if equity_log_file:
            equity_log_file.flush()
            equity_log_file.close()

    processed_steps = max(0, last_idx - start_idx + 1)
    if current_trade_growth is not None:
        terminal_closes += 1
        trade_pnls.append(float(current_trade_growth - 1.0))
        trade_costs.append(float(current_trade_cost))
        if current_trade_start_step is not None:
            holding_steps.append(processed_steps - current_trade_start_step + 1)

    total_return = state.equity - 1.0
    sharpe = compute_sharpe_ratio_from_equity(equity_series)
    action_avg = action_sum / processed_steps if processed_steps > 0 else 0.0
    action_abs_avg = action_abs_sum / processed_steps if processed_steps > 0 else 0.0
    total_actions = action_long + action_short + action_flat
    long_ratio = 0.0
    short_ratio = 0.0
    flat_ratio = 1.0
    if total_actions > 0:
        long_ratio = action_long / total_actions
        short_ratio = action_short / total_actions
        flat_ratio = action_flat / total_actions

    closed_trades = len(trade_pnls)
    trade_rate_1k = (closed_trades * 1000.0 / processed_steps) if processed_steps > 0 else 0.0
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

    end_index = last_idx if last_idx >= 0 else start_idx
    start_ts = bundle.timestamps[start_idx] if start_idx < len(bundle.timestamps) else "-"
    end_ts = bundle.timestamps[end_index] if end_index < len(bundle.timestamps) else "-"
    return PlaybackResult(
        start_index=start_idx,
        end_index=end_index,
        processed_steps=processed_steps,
        trades=closed_trades,
        equity=state.equity,
        total_return=total_return,
        sharpe=sharpe,
        max_drawdown=max_drawdown,
        trade_pnls=trade_pnls,
        trade_costs=trade_costs,
        holding_steps=holding_steps,
        opens=opens,
        closes=closes,
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
        start_ts=start_ts,
        end_ts=end_ts,
        drawdown_peak_step=drawdown_peak_step,
        drawdown_trough_step=drawdown_trough_step,
        drawdown_peak_equity=drawdown_peak_equity,
        drawdown_trough_equity=drawdown_trough_equity,
        gate_reasons=gate_reasons,
    )


def print_playback_result(result: PlaybackResult) -> None:
    print(
        f"Done. steps={result.processed_steps} trades={result.trades} "
        f"equity={result.equity:.6f} return={result.total_return:.6f}"
    )
    print(f"Sharpe: {result.sharpe:.6f}")
    print(f"Max drawdown: {result.max_drawdown:.6f}")

    if result.trade_pnls:
        wins = sum(1 for pnl in result.trade_pnls if pnl > 0)
        avg_net_return = float(np.mean(result.trade_pnls))
        median_net_return = float(np.median(result.trade_pnls))
        p10_net_return = float(np.percentile(result.trade_pnls, 10))
        p90_net_return = float(np.percentile(result.trade_pnls, 90))
        avg_total_cost = float(np.mean(result.trade_costs)) if result.trade_costs else 0.0
        print(
            f"Trade stats: position_changes={result.opens + result.closes + result.reversals + result.resizes} closed_trades={len(result.trade_pnls)} "
            f"opens={result.opens} closes={result.closes} reversals={result.reversals} "
            f"resizes={result.resizes} terminal_closes={result.terminal_closes} "
            f"wins={wins} win_rate={wins / len(result.trade_pnls):.3f} "
            f"avg_net_return={avg_net_return:.6g} median_net_return={median_net_return:.6g} "
            f"p10_net_return={p10_net_return:.6g} p90_net_return={p90_net_return:.6g} "
            f"avg_total_cost={avg_total_cost:.6g} avg_abs_position={result.action_abs_avg:.6g}"
        )
        max_win, max_loss = _streak_stats(result.trade_pnls)
        print(f"Streak stats: max_win={max_win} max_loss={max_loss}")

    if result.holding_steps:
        avg_hold = float(np.mean(result.holding_steps))
        max_hold = max(result.holding_steps)
        print(f"Holding stats: max_steps={max_hold} avg_steps={avg_hold:.2f}")

    print(
        "Action distribution: long={0:.3f} short={1:.3f} flat={2:.3f} avg={3:.6f} avg_abs={4:.6f}".format(
            result.long_ratio,
            result.short_ratio,
            result.flat_ratio,
            result.action_avg,
            result.action_abs_avg,
        )
    )
    print(f"Trade rate/1k: {result.trade_rate_1k:.2f}")
    print(f"Long-short imbalance: {result.ls_imbalance:.3f}")

    if result.gate_reasons:
        print(f"Quality gate: FAIL ({'; '.join(result.gate_reasons)})")
    else:
        print("Quality gate: PASS")
    print(
        "Drawdown window: peak_step={0} peak_equity={1:.6f} "
        "trough_step={2} trough_equity={3:.6f}".format(
            result.drawdown_peak_step,
            result.drawdown_peak_equity,
            result.drawdown_trough_step,
            result.drawdown_trough_equity,
        )
    )
    print(f"Playback range: start={result.start_ts} end={result.end_ts} steps={result.processed_steps}")


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run PPO inference and simulate trades on historical data.")
    parser.add_argument("--data", required=True, help="Path to raw history CSV.")
    parser.add_argument("--model", default=DEFAULT_MODEL_PATH, help="Path to trained PPO model.")
    parser.add_argument(
        "--feature-scaler",
        default="",
        help="Optional feature scaler JSON (default: model path with .scaler.json).",
    )
    parser.add_argument(
        "--env-config",
        default="",
        help="Optional env config JSON (default: model path with .env.json).",
    )
    parser.add_argument(
        "--stochastic",
        action="store_true",
        help="Use stochastic actions (deterministic=False) for diagnostics.",
    )
    parser.add_argument("--log-every", type=int, default=200, help="Log every N steps.")
    parser.add_argument("--start-index", type=int, default=0, help="Zero-based bar index to start playback from.")
    parser.add_argument("--max-steps", type=int, default=0, help="Limit steps (0 = full length).")
    parser.add_argument(
        "--session-filter",
        choices=("all", "monday_open", "london", "ny", "overlap"),
        default="all",
        help="Optional session filter applied before playback.",
    )
    parser.add_argument("--transaction-cost-bps", type=float, default=1.0, help="Transaction cost in bps.")
    parser.add_argument("--slippage-bps", type=float, default=0.5, help="Slippage in bps.")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-step logs; print summary only.")
    parser.add_argument("--equity-log", default="", help="Optional CSV path to append step,equity.")
    parser.add_argument("--equity-log-every", type=int, default=200, help="Write equity log every N steps.")
    parser.add_argument(
        "--baseline",
        choices=("none", "flat", "long", "short", "all"),
        default="all",
        help="Baseline comparison mode.",
    )
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    bundle = load_playback_bundle(
        data_path=args.data,
        model_path=args.model,
        feature_scaler_path=args.feature_scaler,
        env_config_path=args.env_config,
        session_filter=args.session_filter,
        transaction_cost_bps=args.transaction_cost_bps,
        slippage_bps=args.slippage_bps,
    )

    stop_requested = False

    def _request_stop(*_args) -> None:
        nonlocal stop_requested
        stop_requested = True

    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)

    try:
        result = run_playback(
            bundle,
            start_index=args.start_index,
            max_steps=args.max_steps,
            stochastic=args.stochastic,
            log_every=args.log_every,
            quiet=args.quiet,
            equity_log_path=args.equity_log,
            equity_log_every=args.equity_log_every,
            should_stop=lambda: stop_requested,
        )
    except ValueError as exc:
        print(str(exc))
        return

    if stop_requested and not args.quiet:
        print("Stopped early.")
    print_playback_result(result)

    if args.baseline != "none":
        modes = {"flat": 0.0, "long": 1.0, "short": -1.0}
        selected = modes if args.baseline == "all" else {args.baseline: modes[args.baseline]}
        for name, position in selected.items():
            equity, ret = simulate_fixed_position(bundle, position, result.start_index, result.processed_steps)
            print(f"Baseline {name}: equity={equity:.6f} return={ret:.6f}")


if __name__ == "__main__":
    main()
