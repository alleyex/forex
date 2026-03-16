from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from forex.ml.rl.features.feature_builder import build_feature_frame, load_csv
from forex.ml.rl.features.feature_snr import compute_feature_snr_report


def _parse_horizons(raw: str) -> list[int]:
    values = []
    for part in raw.split(","):
        item = part.strip()
        if not item:
            continue
        horizon = int(item)
        if horizon <= 0:
            raise ValueError("Forward return horizons must be > 0.")
        values.append(horizon)
    if not values:
        raise ValueError("At least one horizon is required.")
    return values


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate feature edge using IC, rank IC, sign Sharpe, and quantile spreads."
    )
    parser.add_argument("--data", required=True, help="Path to raw history CSV.")
    parser.add_argument(
        "--horizons",
        default="1,5,20",
        help="Comma-separated forward return horizons in bars.",
    )
    parser.add_argument(
        "--quantile",
        type=float,
        default=0.2,
        help="Top/bottom quantile threshold used for spread statistics.",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=50,
        help="Minimum aligned rows required before a feature/horizon pair is considered valid.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=15,
        help="Number of top-ranked features to print.",
    )
    parser.add_argument("--json-out", default="", help="Optional JSON output path.")
    parser.add_argument(
        "--csv-out",
        default="",
        help="Optional CSV output path for per-horizon rows.",
    )
    return parser


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "feature",
        "horizon",
        "sample_count",
        "valid",
        "ic",
        "rank_ic",
        "target_vol",
        "sign_mean_return",
        "sign_sharpe",
        "signal_to_noise",
        "top_quantile_return",
        "bottom_quantile_return",
        "top_bottom_spread",
        "active_fraction",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    horizons = _parse_horizons(args.horizons)
    df = load_csv(args.data)
    features, closes, _ = build_feature_frame(df)
    report = compute_feature_snr_report(
        features,
        closes,
        horizons=horizons,
        quantile=float(args.quantile),
        min_samples=int(args.min_samples),
    )

    top_k = max(1, int(args.top_k))
    feature_summary = list(report["feature_summary"])
    print(
        "Feature SNR:",
        f"rows={report['rows']}",
        f"features={report['feature_count']}",
        f"horizons={','.join(str(item) for item in report['horizons'])}",
        f"quantile={report['quantile']:.2f}",
    )
    print("")
    print("Top features:")
    for rank, row in enumerate(feature_summary[:top_k], start=1):
        print(
            f"{rank:>2}. {row['feature']}: "
            f"score={float(row['summary_score']):.6f} "
            f"abs_ic={float(row['avg_abs_ic']):.6f} "
            f"abs_rank_ic={float(row['avg_abs_rank_ic']):.6f} "
            f"sign_sharpe={float(row['avg_sign_sharpe']):.6f} "
            f"snr={float(row['avg_signal_to_noise']):.6f} "
            f"spread={float(row['avg_abs_top_bottom_spread']):.6f} "
            f"valid_horizons={int(row['valid_horizons'])}"
        )

    json_out = str(args.json_out).strip()
    if json_out:
        json_path = Path(json_out).expanduser()
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(report, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )

    csv_out = str(args.csv_out).strip()
    if csv_out:
        _write_csv(Path(csv_out).expanduser(), list(report["long_rows"]))


if __name__ == "__main__":
    main()
