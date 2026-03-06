from __future__ import annotations

import pandas as pd
import pytest

from forex.ml.rl.features.feature_snr import compute_feature_snr_report, compute_forward_returns


def test_compute_forward_returns_matches_expected_percent_changes() -> None:
    closes = [100.0, 110.0, 121.0, 133.1]

    result = compute_forward_returns(closes, [1, 2])

    assert result["forward_return_1"].tolist()[:3] == pytest.approx([0.1, 0.1, 0.1])
    assert result["forward_return_2"].tolist()[:2] == pytest.approx([0.21, 0.21])


def test_compute_feature_snr_report_ranks_predictive_feature_above_noise() -> None:
    features = pd.DataFrame(
        {
            "predictive": [1.0, 2.0, 3.0, 4.0, 5.0],
            "noise": [0.0, 1.0, 0.0, 1.0, 0.0],
        }
    )
    closes = pd.Series([100.0, 101.0, 103.0, 106.0, 110.0])

    report = compute_feature_snr_report(
        features,
        closes,
        horizons=(1,),
        quantile=0.4,
        min_samples=3,
    )

    summary = {row["feature"]: row for row in report["feature_summary"]}
    predictive = summary["predictive"]
    noise = summary["noise"]

    assert predictive["summary_score"] > noise["summary_score"]
    assert predictive["avg_abs_ic"] > noise["avg_abs_ic"]
    assert predictive["avg_abs_rank_ic"] > noise["avg_abs_rank_ic"]


def test_compute_feature_snr_report_marks_short_series_as_invalid() -> None:
    features = pd.DataFrame({"x": [1.0, 2.0, 3.0]})
    closes = pd.Series([100.0, 101.0, 102.0])

    report = compute_feature_snr_report(
        features,
        closes,
        horizons=(1,),
        min_samples=10,
    )

    row = report["long_rows"][0]
    assert row["valid"] is False
    assert report["feature_summary"][0]["valid_horizons"] == 0
