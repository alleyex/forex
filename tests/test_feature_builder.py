from __future__ import annotations

import numpy as np
import pandas as pd

from forex.ml.rl.features.feature_builder import build_feature_frame


def test_build_feature_frame_exposes_extended_feature_set() -> None:
    rows = 120
    base = np.linspace(100.0, 120.0, num=rows, dtype=np.float64)
    wave = np.sin(np.linspace(0.0, 12.0, num=rows)) * 0.8
    close = base + wave
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=rows, freq="15min").astype(str),
            "open": close - 0.1,
            "close": close,
            "high": close + 0.4,
            "low": close - 0.4,
            "volume": np.linspace(1000.0, 2000.0, num=rows),
        }
    )

    features, closes, timestamps = build_feature_frame(df)

    expected_columns = {
        "returns_1",
        "returns_5",
        "returns_10",
        "returns_20",
        "sma_10",
        "sma_20",
        "sma_50",
        "momentum_10_20",
        "momentum_20_50",
        "price_z_20",
        "price_z_50",
        "price_z_100",
        "breakout_20",
        "breakout_50",
        "rsi_14",
        "atr_14",
        "atr_ratio_14_50",
        "atr_ratio_14_100",
        "vol_ratio_10_50",
        "bollinger_band_width_20",
        "distance_to_rolling_high_20",
        "distance_to_rolling_low_20",
        "body_size_ratio",
        "close_location_in_bar",
        "adx_14",
        "vol_z",
        "hour_sin",
        "hour_cos",
        "weekday_sin",
        "weekday_cos",
        "minute_of_week_sin",
        "minute_of_week_cos",
        "is_monday_open_window",
        "is_london_session",
        "is_ny_session",
        "is_london_ny_overlap",
    }
    assert expected_columns.issubset(features.columns)
    assert len(features) == len(closes) == len(timestamps)
    assert not features.isna().any().any()


def test_build_feature_frame_keeps_uptrend_rows_and_sets_rsi_to_100() -> None:
    rows = 160
    close = np.linspace(100.0, 140.0, num=rows, dtype=np.float64)
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=rows, freq="15min").astype(str),
            "open": close - 0.1,
            "close": close,
            "high": close + 0.4,
            "low": close - 0.4,
            "volume": np.linspace(1000.0, 2000.0, num=rows),
        }
    )

    features, closes, timestamps = build_feature_frame(df)

    assert len(features) > 0
    assert len(features) == len(closes) == len(timestamps)
    assert np.allclose(features["rsi_14"].to_numpy(), 100.0)


def test_build_feature_frame_supports_utc_timestamp_minutes_without_timestamp_column() -> None:
    rows = 160
    close = np.linspace(100.0, 110.0, num=rows, dtype=np.float64)
    df = pd.DataFrame(
        {
            "utc_timestamp_minutes": np.arange(rows),
            "open": close - 0.1,
            "close": close,
            "high": close + 0.4,
            "low": close - 0.4,
            "volume": np.linspace(1000.0, 2000.0, num=rows),
        }
    )

    features, closes, timestamps = build_feature_frame(df)

    assert len(features) > 0
    assert len(features) == len(closes) == len(timestamps)
    assert timestamps[0]


def test_breakout_20_is_not_a_duplicate_of_distance_to_rolling_high_20() -> None:
    rows = 160
    base = np.linspace(100.0, 120.0, num=rows, dtype=np.float64)
    wave = np.sin(np.linspace(0.0, 12.0, num=rows)) * 1.5
    close = base + wave
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=rows, freq="15min").astype(str),
            "open": close - 0.2,
            "close": close,
            "high": close + 0.5,
            "low": close - 0.5,
            "volume": np.linspace(1000.0, 2000.0, num=rows),
        }
    )

    features, _, _ = build_feature_frame(df)

    assert not np.allclose(
        features["breakout_20"].to_numpy(),
        features["distance_to_rolling_high_20"].to_numpy(),
    )
