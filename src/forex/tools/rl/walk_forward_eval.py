from __future__ import annotations

import argparse
import json
import signal
from pathlib import Path

import numpy as np

from forex.tools.rl.run_live_sim import PlaybackResult, load_playback_bundle, run_playback


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


def _compare_results(
    primary_results: list[PlaybackResult],
    compare_results: list[PlaybackResult],
) -> dict[str, object]:
    paired_count = min(len(primary_results), len(compare_results))
    if paired_count <= 0:
        return {
            "segments_compared": 0,
            "primary_return_wins": 0,
            "primary_sharpe_wins": 0,
            "primary_drawdown_wins": 0,
            "primary_gate_wins": 0,
        }

    primary_return_wins = 0
    primary_sharpe_wins = 0
    primary_drawdown_wins = 0
    primary_gate_wins = 0
    for idx in range(paired_count):
        primary = primary_results[idx]
        compare = compare_results[idx]
        if primary.total_return > compare.total_return:
            primary_return_wins += 1
        if primary.sharpe > compare.sharpe:
            primary_sharpe_wins += 1
        if primary.max_drawdown < compare.max_drawdown:
            primary_drawdown_wins += 1
        if (not primary.gate_reasons) and compare.gate_reasons:
            primary_gate_wins += 1

    return {
        "segments_compared": paired_count,
        "primary_return_wins": primary_return_wins,
        "primary_sharpe_wins": primary_sharpe_wins,
        "primary_drawdown_wins": primary_drawdown_wins,
        "primary_gate_wins": primary_gate_wins,
    }


def _print_segment(label: str, result: PlaybackResult) -> None:
    gate_text = (
        "PASS"
        if not result.gate_reasons
        else f"FAIL ({'; '.join(result.gate_reasons)})"
    )
    print(
        f"{label}: range={result.start_ts} -> {result.end_ts} "
        f"return={result.total_return:.6f} sharpe={result.sharpe:.6f} "
        f"max_dd={result.max_drawdown:.6f} "
        f"trade_rate/1k={result.trade_rate_1k:.2f} gate={gate_text}"
    )


def _print_aggregate(label: str, aggregate: dict[str, object]) -> None:
    print(
        f"{label} aggregate: segments={aggregate['segments']} pass={aggregate['pass_count']} "
        f"avg_return={aggregate['avg_return']:.6f} "
        f"avg_sharpe={aggregate['avg_sharpe']:.6f} "
        f"avg_max_dd={aggregate['avg_max_drawdown']:.6f} "
        f"worst_max_dd={aggregate['worst_max_drawdown']:.6f} "
        f"avg_trade_rate/1k={aggregate['avg_trade_rate_1k']:.2f}"
    )


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run segmented walk-forward playback "
            "for one or two PPO models."
        )
    )
    parser.add_argument("--data", required=True, help="Path to raw history CSV.")
    parser.add_argument("--model", required=True, help="Primary PPO model path.")
    parser.add_argument("--feature-scaler", default="", help="Optional primary scaler JSON.")
    parser.add_argument("--env-config", default="", help="Optional primary env config JSON.")
    parser.add_argument(
        "--compare-model",
        default="",
        help="Optional secondary PPO model path.",
    )
    parser.add_argument(
        "--compare-feature-scaler",
        default="",
        help="Optional secondary scaler JSON.",
    )
    parser.add_argument(
        "--compare-env-config",
        default="",
        help="Optional secondary env config JSON.",
    )
    parser.add_argument(
        "--start-index",
        type=int,
        default=0,
        help="Zero-based bar index for the first segment.",
    )
    parser.add_argument(
        "--segment-steps",
        type=int,
        default=5000,
        help="Playback steps per segment.",
    )
    parser.add_argument(
        "--segments",
        type=int,
        default=3,
        help="Maximum number of segments to run.",
    )
    parser.add_argument(
        "--stride",
        type=int,
        default=10000,
        help="Index stride between segment starts.",
    )
    parser.add_argument(
        "--session-filter",
        choices=("all", "monday_open", "london", "london_pre_ny", "ny", "overlap"),
        default="all",
        help="Optional session filter applied before playback.",
    )
    parser.add_argument(
        "--transaction-cost-bps",
        type=float,
        default=1.0,
        help="Transaction cost in bps.",
    )
    parser.add_argument("--slippage-bps", type=float, default=0.5, help="Slippage in bps.")
    parser.add_argument(
        "--action-gate",
        action="append",
        default=[],
        help="Optional execution gate feature:min:max.",
    )
    parser.add_argument(
        "--action-gate-mode",
        choices=("force_flat", "entry_only"),
        default="force_flat",
        help="How action gates affect open positions.",
    )
    parser.add_argument(
        "--action-scale",
        type=float,
        default=1.0,
        help="Multiplier applied to raw policy actions before replay envelope logic.",
    )
    parser.add_argument(
        "--threshold-bump",
        action="append",
        default=[],
        help="Optional regime threshold bump feature:min:max:bump.",
    )
    parser.add_argument(
        "--long-threshold",
        type=float,
        default=None,
        help="Optional long entry threshold for policy envelope.",
    )
    parser.add_argument(
        "--short-threshold",
        type=float,
        default=None,
        help="Optional short entry threshold for policy envelope.",
    )
    parser.add_argument(
        "--long-exit-threshold",
        type=float,
        default=None,
        help="Optional long exit threshold.",
    )
    parser.add_argument(
        "--short-exit-threshold",
        type=float,
        default=None,
        help="Optional short exit threshold.",
    )
    parser.add_argument(
        "--stochastic",
        action="store_true",
        help="Use stochastic actions for diagnostics.",
    )
    parser.add_argument("--json-out", default="", help="Optional JSON output path.")
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    if args.segment_steps <= 0:
        parser.error("--segment-steps must be > 0")
    if args.segments <= 0:
        parser.error("--segments must be > 0")
    if args.stride <= 0:
        parser.error("--stride must be > 0")
    policy_enabled = (
        args.long_threshold is not None
        or args.short_threshold is not None
        or bool(list(args.action_gate))
        or bool(list(args.threshold_bump))
    )
    if policy_enabled:
        if args.long_threshold is None or args.short_threshold is None:
            parser.error(
                "--long-threshold and --short-threshold are required "
                "when policy envelope options are used"
            )
        if float(args.short_threshold) >= float(args.long_threshold):
            parser.error("--short-threshold must be < --long-threshold")
        long_exit_threshold = (
            float(args.long_threshold)
            if args.long_exit_threshold is None
            else float(args.long_exit_threshold)
        )
        short_exit_threshold = (
            float(args.short_threshold)
            if args.short_exit_threshold is None
            else float(args.short_exit_threshold)
        )
        if long_exit_threshold > float(args.long_threshold):
            parser.error("--long-exit-threshold must be <= --long-threshold")
        if short_exit_threshold < float(args.short_threshold):
            parser.error("--short-exit-threshold must be >= --short-threshold")
        if short_exit_threshold >= long_exit_threshold:
            parser.error("--short-exit-threshold must be < --long-exit-threshold")
    else:
        long_exit_threshold = None
        short_exit_threshold = None

    primary_bundle = load_playback_bundle(
        data_path=args.data,
        model_path=args.model,
        feature_scaler_path=args.feature_scaler,
        env_config_path=args.env_config,
        session_filter=args.session_filter,
        transaction_cost_bps=args.transaction_cost_bps,
        slippage_bps=args.slippage_bps,
        action_gates=list(args.action_gate),
        action_gate_mode=str(args.action_gate_mode),
        action_scale=float(args.action_scale),
        threshold_bumps=list(args.threshold_bump),
        long_threshold=args.long_threshold,
        short_threshold=args.short_threshold,
        long_exit_threshold=long_exit_threshold,
        short_exit_threshold=short_exit_threshold,
    )
    compare_bundle = None
    if args.compare_model.strip():
        compare_bundle = load_playback_bundle(
            data_path=args.data,
            model_path=args.compare_model,
            feature_scaler_path=args.compare_feature_scaler,
            env_config_path=args.compare_env_config,
            session_filter=args.session_filter,
            transaction_cost_bps=args.transaction_cost_bps,
            slippage_bps=args.slippage_bps,
            action_gates=list(args.action_gate),
            action_gate_mode=str(args.action_gate_mode),
            action_scale=float(args.action_scale),
            threshold_bumps=list(args.threshold_bump),
            long_threshold=args.long_threshold,
            short_threshold=args.short_threshold,
            long_exit_threshold=long_exit_threshold,
            short_exit_threshold=short_exit_threshold,
        )

    primary_label = Path(args.model).stem
    compare_label = Path(args.compare_model).stem if compare_bundle else ""
    primary_results: list[PlaybackResult] = []
    compare_results: list[PlaybackResult] = []
    stop_requested = False

    def _request_stop(*_args) -> None:
        nonlocal stop_requested
        stop_requested = True

    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)

    for segment_idx in range(args.segments):
        if stop_requested:
            break
        current_start = args.start_index + segment_idx * args.stride
        try:
            primary_result = run_playback(
                primary_bundle,
                start_index=current_start,
                max_steps=args.segment_steps,
                stochastic=args.stochastic,
                quiet=True,
            )
        except ValueError:
            break
        primary_results.append(primary_result)
        print(f"Segment {segment_idx + 1} start_index={current_start}")
        _print_segment(primary_label, primary_result)

        if compare_bundle is not None:
            compare_result = run_playback(
                compare_bundle,
                start_index=current_start,
                max_steps=args.segment_steps,
                stochastic=args.stochastic,
                quiet=True,
            )
            compare_results.append(compare_result)
            _print_segment(compare_label, compare_result)

    primary_aggregate = _aggregate_results(primary_results)
    compare_aggregate = _aggregate_results(compare_results) if compare_results else None
    comparison = _compare_results(primary_results, compare_results) if compare_results else None

    print("")
    _print_aggregate(primary_label, primary_aggregate)
    if compare_aggregate is not None:
        _print_aggregate(compare_label, compare_aggregate)
    if comparison is not None:
        print(
            f"Comparison: segments={comparison['segments_compared']} "
            f"{primary_label}_return_wins={comparison['primary_return_wins']} "
            f"{primary_label}_sharpe_wins={comparison['primary_sharpe_wins']} "
            f"{primary_label}_drawdown_wins={comparison['primary_drawdown_wins']} "
            f"{primary_label}_gate_wins={comparison['primary_gate_wins']}"
        )

    if args.json_out.strip():
        output_path = Path(args.json_out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "data": args.data,
            "segment_steps": args.segment_steps,
            "segments_requested": args.segments,
            "segments_completed": len(primary_results),
            "stride": args.stride,
            "start_index": args.start_index,
            "session_filter": args.session_filter,
            "primary_model": args.model,
            "compare_model": args.compare_model or None,
            "primary_aggregate": primary_aggregate,
            "compare_aggregate": compare_aggregate,
            "comparison": comparison,
            "segments": [
                {
                    "segment": idx + 1,
                    "primary": _result_to_dict(primary_results[idx]),
                    "compare": (
                        _result_to_dict(compare_results[idx])
                        if idx < len(compare_results)
                        else None
                    ),
                }
                for idx in range(len(primary_results))
            ],
        }
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Saved JSON: {output_path}")


if __name__ == "__main__":
    main()
