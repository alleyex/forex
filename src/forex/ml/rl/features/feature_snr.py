from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd


def compute_forward_returns(
    closes: Sequence[float] | np.ndarray | pd.Series,
    horizons: Sequence[int],
) -> pd.DataFrame:
    close_series = pd.Series(closes, dtype=np.float64).reset_index(drop=True)
    payload: dict[str, pd.Series] = {}
    for horizon in horizons:
        horizon_int = int(horizon)
        if horizon_int <= 0:
            raise ValueError("Forward return horizons must be > 0.")
        payload[f"forward_return_{horizon_int}"] = (
            close_series.shift(-horizon_int) / close_series - 1.0
        )
    return pd.DataFrame(payload)


def compute_feature_snr_report(
    features: pd.DataFrame,
    closes: Sequence[float] | np.ndarray | pd.Series,
    *,
    horizons: Sequence[int] = (1, 5, 20),
    quantile: float = 0.2,
    min_samples: int = 50,
) -> dict[str, object]:
    if features.empty:
        return {
            "horizons": [int(h) for h in horizons],
            "quantile": float(quantile),
            "min_samples": int(min_samples),
            "feature_count": 0,
            "rows": 0,
            "long_rows": [],
            "feature_summary": [],
        }

    if not 0.0 < float(quantile) < 0.5:
        raise ValueError("quantile must be in (0, 0.5).")

    feature_frame = features.reset_index(drop=True).copy()
    forward_returns = compute_forward_returns(closes, horizons).reset_index(drop=True)
    if len(feature_frame) != len(forward_returns):
        raise ValueError("features and closes must have matching lengths.")

    long_rows: list[dict[str, float | int | str | bool]] = []
    summary_rows: list[dict[str, float | int | str]] = []

    for feature_name in feature_frame.columns:
        per_feature_rows: list[dict[str, float | int | str | bool]] = []
        feature_series = pd.to_numeric(feature_frame[feature_name], errors="coerce")
        for horizon in horizons:
            horizon_int = int(horizon)
            target_name = f"forward_return_{horizon_int}"
            aligned = pd.DataFrame(
                {
                    "feature": feature_series,
                    "target": forward_returns[target_name],
                }
            ).dropna()
            sample_count = int(len(aligned))
            if sample_count <= 0:
                row = {
                    "feature": feature_name,
                    "horizon": horizon_int,
                    "sample_count": 0,
                    "valid": False,
                    "ic": 0.0,
                    "rank_ic": 0.0,
                    "target_vol": 0.0,
                    "sign_mean_return": 0.0,
                    "sign_sharpe": 0.0,
                    "signal_to_noise": 0.0,
                    "top_quantile_return": 0.0,
                    "bottom_quantile_return": 0.0,
                    "top_bottom_spread": 0.0,
                    "active_fraction": 0.0,
                }
                long_rows.append(row)
                per_feature_rows.append(row)
                continue

            x = aligned["feature"].astype(np.float64)
            y = aligned["target"].astype(np.float64)
            target_vol = float(y.std(ddof=0))
            ic = float(x.corr(y)) if sample_count >= 2 else 0.0
            rank_ic = (
                float(x.rank(method="average").corr(y.rank(method="average")))
                if sample_count >= 2
                else 0.0
            )
            if not np.isfinite(ic):
                ic = 0.0
            if not np.isfinite(rank_ic):
                rank_ic = 0.0

            signal = np.sign(x.to_numpy(dtype=np.float64))
            active_mask = signal != 0.0
            active_fraction = float(np.mean(active_mask)) if len(signal) > 0 else 0.0
            if np.any(active_mask):
                signed_returns = signal[active_mask] * y.to_numpy(dtype=np.float64)[active_mask]
                sign_mean_return = float(np.mean(signed_returns))
                sign_std = float(np.std(signed_returns))
                sign_sharpe = float(sign_mean_return / sign_std) if sign_std > 1e-12 else 0.0
            else:
                sign_mean_return = 0.0
                sign_sharpe = 0.0

            signal_to_noise = (
                float(sign_mean_return / target_vol) if target_vol > 1e-12 else 0.0
            )

            lo = float(x.quantile(float(quantile)))
            hi = float(x.quantile(1.0 - float(quantile)))
            top_bucket = y[x >= hi]
            bottom_bucket = y[x <= lo]
            top_quantile_return = float(top_bucket.mean()) if len(top_bucket) > 0 else 0.0
            bottom_quantile_return = (
                float(bottom_bucket.mean()) if len(bottom_bucket) > 0 else 0.0
            )
            top_bottom_spread = float(top_quantile_return - bottom_quantile_return)
            valid = bool(sample_count >= int(min_samples))
            row = {
                "feature": feature_name,
                "horizon": horizon_int,
                "sample_count": sample_count,
                "valid": valid,
                "ic": ic,
                "rank_ic": rank_ic,
                "target_vol": target_vol,
                "sign_mean_return": sign_mean_return,
                "sign_sharpe": sign_sharpe,
                "signal_to_noise": signal_to_noise,
                "top_quantile_return": top_quantile_return,
                "bottom_quantile_return": bottom_quantile_return,
                "top_bottom_spread": top_bottom_spread,
                "active_fraction": active_fraction,
            }
            long_rows.append(row)
            per_feature_rows.append(row)

        valid_rows = [row for row in per_feature_rows if bool(row["valid"])]
        source_rows = valid_rows if valid_rows else per_feature_rows
        avg_abs_ic = float(np.mean([abs(float(row["ic"])) for row in source_rows]))
        avg_abs_rank_ic = float(np.mean([abs(float(row["rank_ic"])) for row in source_rows]))
        avg_sign_sharpe = float(np.mean([float(row["sign_sharpe"]) for row in source_rows]))
        avg_signal_to_noise = float(
            np.mean([float(row["signal_to_noise"]) for row in source_rows])
        )
        avg_abs_spread = float(
            np.mean([abs(float(row["top_bottom_spread"])) for row in source_rows])
        )
        valid_horizons = int(sum(1 for row in per_feature_rows if bool(row["valid"])))
        summary_score = (
            2.0 * avg_abs_rank_ic
            + 1.0 * avg_abs_ic
            + 1.0 * avg_sign_sharpe
            + 0.5 * avg_signal_to_noise
            + 0.5 * avg_abs_spread
        )
        summary_rows.append(
            {
                "feature": feature_name,
                "valid_horizons": valid_horizons,
                "avg_abs_ic": avg_abs_ic,
                "avg_abs_rank_ic": avg_abs_rank_ic,
                "avg_sign_sharpe": avg_sign_sharpe,
                "avg_signal_to_noise": avg_signal_to_noise,
                "avg_abs_top_bottom_spread": avg_abs_spread,
                "summary_score": float(summary_score),
            }
        )

    summary_rows.sort(
        key=lambda row: (
            float(row["summary_score"]),
            float(row["avg_abs_rank_ic"]),
            float(row["avg_sign_sharpe"]),
        ),
        reverse=True,
    )
    return {
        "horizons": [int(h) for h in horizons],
        "quantile": float(quantile),
        "min_samples": int(min_samples),
        "feature_count": int(feature_frame.shape[1]),
        "rows": int(len(feature_frame)),
        "long_rows": long_rows,
        "feature_summary": summary_rows,
    }
