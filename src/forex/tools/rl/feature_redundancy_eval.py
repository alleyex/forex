from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from forex.ml.rl.features.feature_builder import (
    build_feature_frame,
    filter_feature_rows_by_session,
    load_csv,
)
from forex.ml.rl.features.feature_redundancy import compute_feature_redundancy_report


def _parse_horizons(raw: str) -> list[int]:
    values: list[int] = []
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
        description=(
            "Report redundant features and low-signal noise candidates "
            "using Spearman correlation and SNR."
        )
    )
    parser.add_argument("--data", required=True, help="Path to raw history CSV.")
    parser.add_argument(
        "--session-filter",
        default="all",
        choices=("all", "monday_open", "london", "london_pre_ny", "ny", "overlap"),
        help="Optional session subset.",
    )
    parser.add_argument(
        "--horizons",
        default="1,5,20",
        help="Comma-separated forward return horizons in bars.",
    )
    parser.add_argument(
        "--quantile",
        type=float,
        default=0.2,
        help="Top/bottom quantile threshold for SNR stats.",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=50,
        help="Minimum aligned rows for valid SNR rows.",
    )
    parser.add_argument(
        "--corr-threshold",
        type=float,
        default=0.90,
        help="Absolute Spearman threshold used to group redundant features.",
    )
    parser.add_argument(
        "--noise-quantile",
        type=float,
        default=0.35,
        help="Bottom score quantile used to flag noise candidates.",
    )
    parser.add_argument("--top-k", type=int, default=15, help="Rows to print for each section.")
    parser.add_argument("--json-out", default="", help="Optional JSON output path.")
    parser.add_argument(
        "--csv-out",
        default="",
        help="Optional CSV output path for feature rows.",
    )
    return parser


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "feature",
                "summary_score",
                "avg_abs_ic",
                "avg_abs_rank_ic",
                "avg_sign_sharpe",
                "valid_horizons",
                "max_abs_spearman",
                "most_similar_feature",
                "stronger_correlated_feature",
                "group_id",
                "representative",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    horizons = _parse_horizons(args.horizons)
    df = load_csv(str(args.data))
    features, closes, timestamps = build_feature_frame(df)
    features, closes, timestamps = filter_feature_rows_by_session(
        features,
        closes,
        timestamps,
        str(args.session_filter),
    )
    report = compute_feature_redundancy_report(
        features,
        closes,
        horizons=horizons,
        quantile=float(args.quantile),
        min_samples=int(args.min_samples),
        corr_threshold=float(args.corr_threshold),
        noise_quantile=float(args.noise_quantile),
    )
    top_k = max(1, int(args.top_k))

    print(
        "Feature redundancy:",
        f"rows={report['rows']}",
        f"features={report['feature_count']}",
        f"session={str(args.session_filter)}",
        f"corr_threshold={float(report['corr_threshold']):.2f}",
        f"noise_quantile={float(report['noise_quantile']):.2f}",
    )
    print("")
    print("Redundancy groups:")
    groups = list(report["redundancy_groups"])
    if not groups:
        print("  none")
    for group in groups[:top_k]:
        member_text = ", ".join(
            f"{item['feature']}({float(item['summary_score']):.4f})"
            for item in list(group["members"])[:8]
        )
        print(
            f"  group {int(group['group_id'])}: "
            f"rep={group['representative']} size={int(group['size'])} members={member_text}"
        )

    print("")
    print("Noise candidates:")
    noise_rows = list(report["noise_candidates"])
    if not noise_rows:
        print("  none")
    for row in noise_rows[:top_k]:
        print(
            f"  {row['feature']}: "
            f"score={float(row['summary_score']):.6f} "
            f"rank_ic={float(row['avg_abs_rank_ic']):.6f} "
            f"max_abs_spearman={float(row['max_abs_spearman']):.3f} "
            f"similar={row['most_similar_feature'] or '-'} "
            f"reasons={','.join(str(item) for item in row['reasons'])}"
        )

    json_out = str(args.json_out).strip()
    if json_out:
        json_path = Path(json_out).expanduser()
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")

    csv_out = str(args.csv_out).strip()
    if csv_out:
        _write_csv(Path(csv_out).expanduser(), list(report["feature_rows"]))


if __name__ == "__main__":
    main()
