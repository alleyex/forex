from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from forex.ml.rl.features.feature_builder import build_feature_frame, filter_feature_rows_by_session, load_csv
from forex.tools.rl.supervised_baseline_eval import _apply_feature_gates, _build_gate_mask, _build_targets

DEFAULT_FEATURES = [
    "pre_london_compression",
    "asia_range_width_atr",
    "volatility_regime_z",
    "vol_pct_72_252",
    "ny_reversal_pressure",
]


def _segment_label_stats(labels: np.ndarray) -> dict[str, float]:
    total = max(1, int(len(labels)))
    positives = int(np.sum(labels > 0))
    negatives = int(np.sum(labels < 0))
    nonzero = positives + negatives
    return {
        "rows": float(total),
        "positive_ratio": float(positives / total),
        "negative_ratio": float(negatives / total),
        "nonzero_ratio": float(nonzero / total),
    }


def _segment_feature_stats(frame: pd.DataFrame, feature_names: list[str]) -> dict[str, dict[str, float]]:
    stats: dict[str, dict[str, float]] = {}
    for name in feature_names:
        if name not in frame.columns:
            continue
        values = frame[name].to_numpy(dtype=np.float64, copy=False)
        stats[name] = {
            "mean": float(np.mean(values)) if len(values) else 0.0,
            "median": float(np.median(values)) if len(values) else 0.0,
        }
    return stats


def _pick_focus_segment(segments: list[dict[str, object]], focus_segment: int | None) -> int:
    if focus_segment is not None:
        idx = int(focus_segment) - 1
        if idx < 0 or idx >= len(segments):
            raise ValueError("--focus-segment is out of range")
        return idx
    returns = [float(segment.get("total_return", 0.0)) for segment in segments]
    return int(np.argmin(np.asarray(returns, dtype=np.float64)))


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Diagnose feature/label differences for supervised walk-forward segments.")
    parser.add_argument("--eval-json", required=True, help="Path to supervised_baseline_eval JSON output.")
    parser.add_argument("--data", required=True, help="Path to raw history CSV used for the evaluation.")
    parser.add_argument(
        "--feature",
        action="append",
        default=[],
        help="Feature name to include in the diagnostic comparison. May be repeated.",
    )
    parser.add_argument("--focus-segment", type=int, default=None, help="1-based segment index to focus on.")
    parser.add_argument("--json-out", default="", help="Optional JSON output path.")
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    payload = json.loads(Path(args.eval_json).read_text(encoding="utf-8"))
    segments = list(payload.get("segments", []))
    if not segments:
        raise ValueError("Evaluation JSON contains no segments")

    feature_names = [str(item).strip() for item in list(args.feature) if str(item).strip()]
    if not feature_names:
        feature_names = list(DEFAULT_FEATURES)

    df = load_csv(str(args.data))
    features_frame, closes, timestamps = build_feature_frame(df)
    features_frame, closes, timestamps = filter_feature_rows_by_session(
        features_frame,
        closes,
        timestamps,
        str(payload.get("session_filter", "all")),
    )
    feature_gates = payload.get("feature_gates", [])
    if feature_gates:
        features_frame, closes, timestamps = _apply_feature_gates(
            features_frame,
            closes,
            timestamps,
            feature_gates,
        )
    action_gate_mask = _build_gate_mask(features_frame, list(payload.get("action_gates", [])))
    labels, _future_returns = _build_targets(
        closes.to_numpy(dtype=np.float32),
        int(payload.get("horizon", 20)),
        float(payload.get("target_threshold", 0.0)),
        target_mode=str(payload.get("target_mode", "forward_return")),
        follow_through_ratio=float(payload.get("follow_through_ratio", 1.25)),
    )

    segment_rows: list[dict[str, object]] = []
    for idx, segment in enumerate(segments):
        start = int(segment["start_index"])
        end = int(segment["end_index"])
        segment_frame = features_frame.iloc[start:end].reset_index(drop=True)
        segment_labels = labels[start:end]
        segment_gate = action_gate_mask[start:end]
        segment_rows.append(
            {
                "segment": idx + 1,
                "start_ts": str(segment.get("start_ts", "")),
                "end_ts": str(segment.get("end_ts", "")),
                "total_return": float(segment.get("total_return", 0.0)),
                "sharpe": float(segment.get("sharpe", 0.0)),
                "max_drawdown": float(segment.get("max_drawdown", 0.0)),
                "trade_rate_1k": float(segment.get("trade_rate_1k", 0.0)),
                "flat_ratio": float(segment.get("flat_ratio", 1.0)),
                "gate_open_ratio": float(np.mean(segment_gate)) if len(segment_gate) else 0.0,
                "label_stats": _segment_label_stats(segment_labels),
                "feature_stats": _segment_feature_stats(segment_frame, feature_names),
            }
        )

    focus_idx = _pick_focus_segment(segments, args.focus_segment)
    focus_row = segment_rows[focus_idx]
    peer_rows = [row for idx, row in enumerate(segment_rows) if idx != focus_idx]
    if not peer_rows:
        raise ValueError("Need at least two segments for diagnostics")

    feature_deltas: dict[str, dict[str, float]] = {}
    for name in feature_names:
        focus_stats = focus_row["feature_stats"].get(name) if isinstance(focus_row["feature_stats"], dict) else None
        peer_stats = [row["feature_stats"].get(name) for row in peer_rows if isinstance(row["feature_stats"], dict)]
        peer_stats = [item for item in peer_stats if item]
        if not focus_stats or not peer_stats:
            continue
        feature_deltas[name] = {
            "focus_mean": float(focus_stats["mean"]),
            "peer_mean": float(np.mean([float(item["mean"]) for item in peer_stats])),
            "focus_median": float(focus_stats["median"]),
            "peer_median": float(np.mean([float(item["median"]) for item in peer_stats])),
        }

    peer_gate_open = float(np.mean([float(row["gate_open_ratio"]) for row in peer_rows]))
    peer_nonzero = float(np.mean([float(row["label_stats"]["nonzero_ratio"]) for row in peer_rows]))
    report = {
        "eval_json": str(args.eval_json),
        "data": str(args.data),
        "focus_segment": int(focus_row["segment"]),
        "focus_range": {
            "start_ts": str(focus_row["start_ts"]),
            "end_ts": str(focus_row["end_ts"]),
        },
        "focus_metrics": {
            "total_return": float(focus_row["total_return"]),
            "sharpe": float(focus_row["sharpe"]),
            "max_drawdown": float(focus_row["max_drawdown"]),
            "trade_rate_1k": float(focus_row["trade_rate_1k"]),
            "flat_ratio": float(focus_row["flat_ratio"]),
            "gate_open_ratio": float(focus_row["gate_open_ratio"]),
            "label_nonzero_ratio": float(focus_row["label_stats"]["nonzero_ratio"]),
        },
        "peer_average": {
            "gate_open_ratio": peer_gate_open,
            "label_nonzero_ratio": peer_nonzero,
        },
        "feature_deltas": feature_deltas,
        "segments": segment_rows,
    }

    print(
        "Focus segment",
        report["focus_segment"],
        f"range={report['focus_range']['start_ts']} -> {report['focus_range']['end_ts']}",
    )
    print(
        "Focus metrics",
        f"return={report['focus_metrics']['total_return']:.6f}",
        f"sharpe={report['focus_metrics']['sharpe']:.6f}",
        f"max_dd={report['focus_metrics']['max_drawdown']:.6f}",
        f"trade_rate/1k={report['focus_metrics']['trade_rate_1k']:.2f}",
        f"flat_ratio={report['focus_metrics']['flat_ratio']:.3f}",
        f"gate_open_ratio={report['focus_metrics']['gate_open_ratio']:.3f}",
        f"label_nonzero_ratio={report['focus_metrics']['label_nonzero_ratio']:.3f}",
    )
    print(
        "Peer average",
        f"gate_open_ratio={report['peer_average']['gate_open_ratio']:.3f}",
        f"label_nonzero_ratio={report['peer_average']['label_nonzero_ratio']:.3f}",
    )
    for name, stats in feature_deltas.items():
        print(
            f"{name}:",
            f"focus_mean={stats['focus_mean']:.6f}",
            f"peer_mean={stats['peer_mean']:.6f}",
            f"focus_median={stats['focus_median']:.6f}",
            f"peer_median={stats['peer_median']:.6f}",
        )

    if args.json_out.strip():
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
