from __future__ import annotations

import numpy as np
import pandas as pd

from forex.ml.rl.features.feature_redundancy import compute_feature_redundancy_report


def test_compute_feature_redundancy_report_clusters_highly_correlated_features() -> None:
    base = np.arange(1.0, 11.0)
    duplicate = base * 1.02
    noise = np.asarray([1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0], dtype=np.float64)
    features = pd.DataFrame(
        {
            "base": base,
            "duplicate": duplicate,
            "noise": noise,
        }
    )
    closes = pd.Series([100.0, 101.0, 103.0, 106.0, 110.0, 115.0, 121.0, 128.0, 136.0, 145.0])

    report = compute_feature_redundancy_report(
        features,
        closes,
        horizons=(1,),
        quantile=0.4,
        min_samples=5,
        corr_threshold=0.95,
        noise_quantile=0.34,
    )

    groups = report["redundancy_groups"]
    assert len(groups) == 1
    group = groups[0]
    assert group["representative"] == "base"
    assert [row["feature"] for row in group["members"]] == ["base", "duplicate"]

    redundant = report["redundant_candidates"][0]
    assert redundant["feature"] == "duplicate"
    assert redundant["representative"] == "base"
    assert redundant["abs_spearman_to_representative"] == 1.0


def test_compute_feature_redundancy_report_flags_low_score_noise_feature() -> None:
    base = np.arange(1.0, 21.0)
    duplicate = base + 0.01
    noise = np.asarray(([0.0, 1.0] * 10), dtype=np.float64)
    features = pd.DataFrame(
        {
            "base": base,
            "duplicate": duplicate,
            "noise": noise,
        }
    )
    closes = pd.Series(np.linspace(100.0, 140.0, num=20))

    report = compute_feature_redundancy_report(
        features,
        closes,
        horizons=(1,),
        quantile=0.4,
        min_samples=10,
        corr_threshold=0.95,
        noise_quantile=0.34,
    )

    noise_rows = {row["feature"]: row for row in report["noise_candidates"]}
    assert "noise" in noise_rows
    assert "low_summary_score" in noise_rows["noise"]["reasons"]
    assert "low_rank_ic" in noise_rows["noise"]["reasons"]
