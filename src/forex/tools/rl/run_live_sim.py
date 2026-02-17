from __future__ import annotations

import argparse
import signal
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from stable_baselines3 import PPO

from forex.ml.rl.envs.trading_env import TradingConfig
from forex.ml.rl.envs.trading_config_io import load_trading_config
from forex.ml.rl.features.feature_builder import (
    apply_scaler,
    build_feature_frame,
    load_csv,
    load_scaler,
)
from forex.config.paths import DEFAULT_MODEL_PATH


@dataclass
class SimState:
    position: float = 0.0
    equity: float = 1.0
    trades: int = 0


def _build_obs(features: np.ndarray, index: int, position: float, max_position: float = 1.0) -> np.ndarray:
    denom = max(1e-6, float(max_position))
    position_norm = position / denom
    return np.concatenate([features[index], np.array([position_norm], dtype=np.float32)]).astype(np.float32)


def _apply_action_constraints(target: float, current_position: float, config: TradingConfig) -> float:
    value = float(target)
    if config.discretize_actions and config.discrete_positions:
        value = min(config.discrete_positions, key=lambda candidate: abs(float(candidate) - value))
    if config.position_step > 0.0:
        value = round(value / config.position_step) * config.position_step
    if config.max_position > 0.0:
        value = float(np.clip(value, -config.max_position, config.max_position))
    if abs(value - current_position) < config.min_position_change:
        value = float(current_position)
    return float(value)


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


def main() -> None:
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
    parser.add_argument("--max-steps", type=int, default=0, help="Limit steps (0 = full length).")
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
    args = parser.parse_args()

    df = load_csv(args.data)
    features_frame, closes, timestamps = build_feature_frame(df)
    scaler_path = args.feature_scaler.strip()
    if not scaler_path:
        scaler_path = str(Path(args.model).with_suffix(".scaler.json"))
    scaler = None
    scaler_file = Path(scaler_path)
    if scaler_file.exists():
        scaler = load_scaler(scaler_file)
        features_frame = apply_scaler(features_frame, scaler)
    features = features_frame.to_numpy(dtype=np.float32)
    closes = closes.to_numpy(dtype=np.float32)

    config = TradingConfig(
        transaction_cost_bps=args.transaction_cost_bps,
        slippage_bps=args.slippage_bps,
        episode_length=None,
        random_start=False,
    )
    env_config_path = args.env_config.strip()
    if not env_config_path:
        env_config_path = str(Path(args.model).with_suffix(".env.json"))
    env_config_file = Path(env_config_path)
    if env_config_file.exists():
        try:
            loaded_config = load_trading_config(env_config_file)
            loaded_config.transaction_cost_bps = float(args.transaction_cost_bps)
            loaded_config.slippage_bps = float(args.slippage_bps)
            loaded_config.episode_length = None
            loaded_config.random_start = False
            config = loaded_config
        except Exception:
            pass
    cost_rate = (config.transaction_cost_bps + config.slippage_bps) / 10000.0
    holding_cost_rate = config.holding_cost_bps / 10000.0

    model = PPO.load(args.model)

    state = SimState()
    max_steps = len(features) - 1
    if args.max_steps > 0:
        max_steps = min(max_steps, args.max_steps)
    if max_steps <= 0:
        print("Not enough rows after feature building; check data columns.")
        return

    stop_requested = False
    equity_log_path = args.equity_log.strip()
    equity_log_every = max(1, int(args.equity_log_every))
    equity_log_fh = None

    def _request_stop(*_args) -> None:
        nonlocal stop_requested
        stop_requested = True

    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)

    if equity_log_path:
        log_path = Path(equity_log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        equity_log_fh = log_path.open("w", encoding="utf-8")
        equity_log_fh.write("step,equity\n")

    def simulate_fixed(position: float, steps: int) -> tuple[float, float]:
        equity = 1.0
        current = 0.0
        for idx in range(steps):
            delta = position - current
            cost = abs(delta) * cost_rate
            holding_cost = abs(current) * holding_cost_rate
            price_return = (closes[idx + 1] - closes[idx]) / closes[idx]
            reward = current * float(price_return) - cost - holding_cost
            equity *= 1.0 + reward
            current = position
        return equity, equity - 1.0

    peak_equity = state.equity
    equity_series = [state.equity]
    max_drawdown = 0.0
    action_sum = 0.0
    action_min = None
    action_max = None
    action_long = 0
    action_short = 0
    action_flat = 0
    last_trade_price = None
    last_change_idx = 0
    trade_pnls: list[float] = []
    trade_costs: list[float] = []
    holding_steps: list[int] = []

    last_idx = -1
    for idx in range(max_steps):
        if stop_requested:
            break
        last_idx = idx
        obs = _build_obs(features, idx, state.position, max_position=config.max_position)
        action, _ = model.predict(obs, deterministic=not args.stochastic)
        target_raw = float(np.clip(action[0], -config.max_position, config.max_position))
        target_position = _apply_action_constraints(target_raw, state.position, config)

        action_sum += target_position
        action_min = target_position if action_min is None else min(action_min, target_position)
        action_max = target_position if action_max is None else max(action_max, target_position)
        if target_position > 0.05:
            action_long += 1
        elif target_position < -0.05:
            action_short += 1
        else:
            action_flat += 1

        delta = target_position - state.position
        if abs(delta) > 1e-6:
            state.trades += 1
            holding_steps.append(idx - last_change_idx)
            last_change_idx = idx

        cost = abs(delta) * cost_rate
        holding_cost = abs(state.position) * holding_cost_rate
        if abs(delta) > 1e-6:
            current_price = closes[idx]
            current_time = timestamps[idx] if idx < len(timestamps) else "-"
            if last_trade_price is not None:
                trade_pnl = state.position * (current_price - last_trade_price) / last_trade_price
                trade_pnls.append(float(trade_pnl))
                trade_costs.append(float(cost))
                if not args.quiet:
                    print(
                        f"Trade @ {current_time} pos={state.position:.3f} -> {target_position:.3f} "
                        f"pnl={trade_pnl:.6g} cost={cost:.6g} holding={holding_cost:.6g}"
                    )
            last_trade_price = current_price

        price_return = (closes[idx + 1] - closes[idx]) / closes[idx]
        reward = state.position * float(price_return) - cost - holding_cost
        state.equity *= 1.0 + reward
        equity_series.append(state.equity)
        state.position = target_position
        if state.equity > peak_equity:
            peak_equity = state.equity
        if peak_equity > 0:
            drawdown = (peak_equity - state.equity) / peak_equity
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        if equity_log_fh and (idx + 1) % equity_log_every == 0:
            equity_log_fh.write(f"{idx + 1},{state.equity:.6f}\n")
            if (idx + 1) % (equity_log_every * 5) == 0:
                equity_log_fh.flush()
        if not args.quiet and args.log_every and (idx + 1) % args.log_every == 0:
            ts = timestamps[idx + 1] if idx + 1 < len(timestamps) else "-"
            print(
                f"[{ts}] step={idx + 1} equity={state.equity:.6f} "
                f"pos={state.position:.3f} reward={reward:.6g}"
            )

    processed_steps = last_idx + 1
    if equity_log_fh:
        equity_log_fh.flush()
        equity_log_fh.close()
    if stop_requested and not args.quiet:
        print("Stopped early.")
    if processed_steps > last_change_idx:
        holding_steps.append(processed_steps - last_change_idx)

    total_return = state.equity - 1.0
    returns = np.diff(np.array(equity_series, dtype=np.float32))
    sharpe = 0.0
    if returns.size > 1:
        mean_ret = float(np.mean(returns))
        std_ret = float(np.std(returns))
        if std_ret > 0:
            sharpe = mean_ret / std_ret

    print(
        f"Done. steps={processed_steps} trades={state.trades} "
        f"equity={state.equity:.6f} return={total_return:.6f}"
    )
    print(f"Sharpe: {sharpe:.6f}")
    print(f"Max drawdown: {max_drawdown:.6f}")

    if trade_pnls:
        wins = sum(1 for pnl in trade_pnls if pnl > 0)
        avg_pnl = float(np.mean(trade_pnls))
        avg_cost = float(np.mean(trade_costs)) if trade_costs else 0.0
        print(
            f"Trade stats: count={len(trade_pnls)} wins={wins} "
            f"win_rate={wins / len(trade_pnls):.3f} avg_pnl={avg_pnl:.6g} avg_cost={avg_cost:.6g}"
        )
        max_win, max_loss = _streak_stats(trade_pnls)
        print(f"Streak stats: max_win={max_win} max_loss={max_loss}")

    if holding_steps:
        avg_hold = float(np.mean(holding_steps))
        max_hold = max(holding_steps)
        print(f"Holding stats: max_steps={max_hold} avg_steps={avg_hold:.2f}")

    action_avg = action_sum / processed_steps if processed_steps > 0 else 0.0
    total_actions = action_long + action_short + action_flat
    if total_actions > 0:
        long_ratio = action_long / total_actions
        short_ratio = action_short / total_actions
        flat_ratio = action_flat / total_actions
        print(
            "Action distribution: long={0:.3f} short={1:.3f} flat={2:.3f} avg={3:.6f}".format(
                long_ratio,
                short_ratio,
                flat_ratio,
                action_avg,
            )
        )

    start_ts = timestamps[0] if timestamps else "-"
    end_ts = timestamps[processed_steps] if processed_steps < len(timestamps) else "-"
    print(f"Playback range: start={start_ts} end={end_ts} steps={processed_steps}")

    if args.baseline != "none":
        modes = {"flat": 0.0, "long": 1.0, "short": -1.0}
        selected = modes if args.baseline == "all" else {args.baseline: modes[args.baseline]}
        for name, pos in selected.items():
            equity, ret = simulate_fixed(pos, processed_steps)
            print(f"Baseline {name}: equity={equity:.6f} return={ret:.6f}")


if __name__ == "__main__":
    main()
