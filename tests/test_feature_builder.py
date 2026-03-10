from __future__ import annotations

import numpy as np
import pandas as pd

import pytest

from forex.ml.rl.features.feature_builder import (
    ALPHA_FEATURE_COLUMNS,
    ALPHA8_FEATURE_COLUMNS,
    ALPHA12_FEATURE_COLUMNS,
    ALPHA16_FEATURE_COLUMNS,
    ALPHA20_FEATURE_COLUMNS,
    ALPHA_SOURCE_COLUMNS,
    CORE20_ALPHA4_FEATURE_COLUMNS,
    CORE20_ALPHA8_FEATURE_COLUMNS,
    CORE20_FEATURE_COLUMNS,
    RESIDUAL_CONTEXT_COLUMNS,
    apply_feature_profile,
    build_feature_frame,
    build_features,
    fit_scaler,
    filter_feature_rows_by_session,
    infer_feature_profile_from_names,
    required_raw_columns_for_profile,
    select_feature_columns,
)


def test_build_feature_frame_exposes_extended_feature_set() -> None:
    rows = 320
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
        "returns_60",
        "sma_10",
        "sma_20",
        "sma_50",
        "momentum_10_20",
        "momentum_20_50",
        "momentum_50_100",
        "price_z_20",
        "price_z_50",
        "price_z_100",
        "distance_to_mean_50",
        "breakout_20",
        "breakout_50",
        "rsi_14",
        "atr_14",
        "atr_ratio_14_50",
        "atr_ratio_14_100",
        "vol_ratio_10_50",
        "vol_pct_72_252",
        "volatility_regime_z",
        "bollinger_band_width_20",
        "distance_to_rolling_high_20",
        "distance_to_rolling_low_20",
        "body_size_ratio",
        "close_location_in_bar",
        "adx_14",
        "trend_flag_25",
        "trend_strength_20_100_atr14",
        "range_strength_10_50_atr14",
        "prev_day_return",
        "prev_day_range_pct",
        "prev_day_range_position",
        "distance_to_prev_day_high",
        "distance_to_prev_day_low",
        "distance_to_day_high_so_far",
        "distance_to_day_low_so_far",
        "since_london_open_return",
        "since_ny_open_return",
        "ny_open_gap_prev_close",
        "london_to_ny_open_return",
        "ny_reversal_pressure",
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


def test_regime_features_have_expected_ranges_and_types() -> None:
    rows = 320
    base = np.linspace(100.0, 130.0, num=rows, dtype=np.float64)
    wave = np.sin(np.linspace(0.0, 24.0, num=rows)) * 2.0
    close = base + wave
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=rows, freq="15min").astype(str),
            "open": close - 0.2,
            "close": close,
            "high": close + 0.6,
            "low": close - 0.6,
            "volume": np.linspace(1000.0, 2000.0, num=rows),
        }
    )

    features, _, _ = build_feature_frame(df)

    vol_pct = features["vol_pct_72_252"].to_numpy()
    trend_flag = features["trend_flag_25"].to_numpy()
    range_strength = features["range_strength_10_50_atr14"].to_numpy()

    assert np.all((vol_pct >= 0.0) & (vol_pct <= 1.0))
    assert set(np.unique(trend_flag)).issubset({0.0, 1.0})
    assert np.all((range_strength > 0.0) & (range_strength <= 1.0))


def test_session_context_features_have_expected_signs() -> None:
    rows = 7 * 24 * 4 * 3
    base = np.linspace(100.0, 118.0, num=rows, dtype=np.float64)
    wave = np.sin(np.linspace(0.0, 18.0, num=rows)) * 1.2
    close = base + wave
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=rows, freq="15min", tz="UTC").astype(str),
            "open": close - 0.1,
            "close": close,
            "high": close + 0.4,
            "low": close - 0.4,
            "volume": np.linspace(1000.0, 2000.0, num=rows),
        }
    )

    features, _, _ = build_feature_frame(df)

    assert np.all(features["distance_to_day_high_so_far"].to_numpy() <= 1e-8)
    assert np.all(features["distance_to_day_low_so_far"].to_numpy() >= -1e-8)
    assert np.all(features["prev_day_range_pct"].to_numpy() > 0.0)
    prev_day_range_position = features["prev_day_range_position"].to_numpy()
    assert np.all(np.isfinite(prev_day_range_position))
    assert np.all((prev_day_range_position >= -2.0) & (prev_day_range_position <= 3.0))
    assert np.all(np.isfinite(features["since_london_open_return"].to_numpy()))
    assert np.all(np.isfinite(features["since_ny_open_return"].to_numpy()))
    assert np.all(np.isfinite(features["ny_open_gap_prev_close"].to_numpy()))
    assert np.all(np.isfinite(features["london_to_ny_open_return"].to_numpy()))
    assert np.all(np.isfinite(features["ny_reversal_pressure"].to_numpy()))


def test_build_feature_frame_keeps_uptrend_rows_and_sets_rsi_to_100() -> None:
    rows = 320
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
    rows = 320
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
    rows = 320
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


def test_select_feature_columns_preserves_requested_order() -> None:
    features = pd.DataFrame(
        {
            "a": [1.0, 2.0],
            "b": [3.0, 4.0],
            "c": [5.0, 6.0],
        }
    )

    selected = select_feature_columns(features, ["c", "a"])

    assert list(selected.columns) == ["c", "a"]


def test_build_feature_frame_supports_selected_feature_subset() -> None:
    rows = 320
    close = np.linspace(100.0, 120.0, num=rows, dtype=np.float64)
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

    selected_names = ["returns_1", "adx_14", "since_ny_open_return", "hour_sin"]
    features, closes, timestamps = build_feature_frame(df, selected_names)

    assert list(features.columns) == selected_names
    assert len(features) == len(closes) == len(timestamps)
    assert not features.isna().any().any()


def test_select_feature_columns_rejects_unknown_names() -> None:
    features = pd.DataFrame({"a": [1.0], "b": [2.0]})

    with pytest.raises(ValueError, match="unknown columns"):
        select_feature_columns(features, ["a", "missing"])


def test_filter_feature_rows_by_session_keeps_only_requested_session_rows() -> None:
    rows = 7 * 24 * 4 * 2
    close = np.linspace(100.0, 110.0, num=rows, dtype=np.float64)
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=rows, freq="15min", tz="UTC").astype(str),
            "open": close - 0.1,
            "close": close,
            "high": close + 0.4,
            "low": close - 0.4,
            "volume": np.linspace(1000.0, 2000.0, num=rows),
        }
    )
    features, closes, timestamps = build_feature_frame(df)

    ny_features, ny_closes, ny_timestamps = filter_feature_rows_by_session(
        features,
        closes,
        timestamps,
        "ny",
    )
    london_features, _, _ = filter_feature_rows_by_session(
        features,
        closes,
        timestamps,
        "london",
    )

    assert len(ny_features) > 0
    assert len(ny_features) == len(ny_closes) == len(ny_timestamps)
    assert (ny_features["is_ny_session"] > 0.5).all()
    assert (london_features["is_london_session"] > 0.5).all()
    assert len(ny_features) < len(features)


def test_filter_feature_rows_by_session_rejects_unknown_name() -> None:
    features = pd.DataFrame({"is_ny_session": [1.0], "x": [2.0]})
    closes = pd.Series([1.0])
    with pytest.raises(ValueError, match="Unknown session filter"):
        filter_feature_rows_by_session(features, closes, ["2024-01-01"], "asia")


def test_apply_feature_profile_alpha_and_residual_shapes() -> None:
    rows = 320
    close = np.linspace(100.0, 120.0, num=rows, dtype=np.float64)
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
    raw_features, _, _ = build_feature_frame(df)

    alpha = apply_feature_profile(raw_features, "alpha4")
    assert list(alpha.columns) == list(ALPHA_FEATURE_COLUMNS)
    assert not alpha.isna().any().any()

    residual = apply_feature_profile(raw_features, "residual")
    expected_residual = [*ALPHA_FEATURE_COLUMNS, *[name for name in RESIDUAL_CONTEXT_COLUMNS if name in raw_features.columns]]
    assert list(residual.columns) == expected_residual
    assert not residual.isna().any().any()
    assert infer_feature_profile_from_names(alpha.columns) == "alpha4"
    assert infer_feature_profile_from_names(residual.columns) == "residual"

    alpha8 = apply_feature_profile(raw_features, "alpha8")
    alpha8_residual = apply_feature_profile(raw_features, "alpha8_residual")
    alpha12 = apply_feature_profile(raw_features, "alpha12")
    alpha16 = apply_feature_profile(raw_features, "alpha16")
    alpha20 = apply_feature_profile(raw_features, "alpha20")
    alpha12_residual = apply_feature_profile(raw_features, "alpha12_residual")
    alpha16_residual = apply_feature_profile(raw_features, "alpha16_residual")
    alpha20_residual = apply_feature_profile(raw_features, "alpha20_residual")
    core20 = apply_feature_profile(raw_features, "core20")
    core20_alpha4 = apply_feature_profile(raw_features, "alpha4_from_core20")
    core20_alpha8 = apply_feature_profile(raw_features, "alpha8_from_core20")

    assert list(alpha8.columns) == list(ALPHA8_FEATURE_COLUMNS)
    assert list(alpha8_residual.columns[: len(ALPHA8_FEATURE_COLUMNS)]) == list(ALPHA8_FEATURE_COLUMNS)
    assert list(alpha12.columns) == list(ALPHA12_FEATURE_COLUMNS)
    assert list(alpha16.columns) == list(ALPHA16_FEATURE_COLUMNS)
    assert list(alpha20.columns) == list(ALPHA20_FEATURE_COLUMNS)
    assert list(alpha12_residual.columns[: len(ALPHA12_FEATURE_COLUMNS)]) == list(ALPHA12_FEATURE_COLUMNS)
    assert list(alpha16_residual.columns[: len(ALPHA16_FEATURE_COLUMNS)]) == list(ALPHA16_FEATURE_COLUMNS)
    assert list(alpha20_residual.columns[: len(ALPHA20_FEATURE_COLUMNS)]) == list(ALPHA20_FEATURE_COLUMNS)
    assert list(core20.columns) == list(CORE20_FEATURE_COLUMNS)
    assert list(core20_alpha4.columns) == list(CORE20_ALPHA4_FEATURE_COLUMNS)
    assert list(core20_alpha8.columns) == list(CORE20_ALPHA8_FEATURE_COLUMNS)
    assert infer_feature_profile_from_names(alpha8.columns) == "alpha8"
    assert infer_feature_profile_from_names(alpha20.columns) == "alpha20"
    assert infer_feature_profile_from_names(alpha8_residual.columns) == "alpha8_residual"
    assert infer_feature_profile_from_names(alpha20_residual.columns) == "alpha20_residual"
    assert infer_feature_profile_from_names(core20.columns) == "core20"
    assert infer_feature_profile_from_names(core20_alpha8.columns) == "alpha8_from_core20"


def test_build_features_infers_profile_from_scaler_names() -> None:
    rows = 320
    close = np.linspace(100.0, 125.0, num=rows, dtype=np.float64)
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
    raw_features, _, _ = build_feature_frame(df)
    residual = apply_feature_profile(raw_features, "residual")
    scaler = fit_scaler(residual)
    bundle = build_features(df, scaler=scaler)
    assert list(bundle.names) == scaler.names
    assert bundle.features.shape[1] == len(scaler.names)


def test_build_features_preserves_alpha8_scaler_profile() -> None:
    rows = 320
    close = np.linspace(100.0, 125.0, num=rows, dtype=np.float64)
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
    raw_features, _, _ = build_feature_frame(df)
    alpha8 = apply_feature_profile(raw_features, "alpha8")
    scaler = fit_scaler(alpha8)
    bundle = build_features(df, scaler=scaler)
    assert list(bundle.names) == scaler.names
    assert bundle.features.shape[1] == len(ALPHA8_FEATURE_COLUMNS)


def test_required_raw_columns_for_profile() -> None:
    assert required_raw_columns_for_profile("raw53") == tuple()
    assert required_raw_columns_for_profile("alpha4") == ALPHA_SOURCE_COLUMNS
    assert required_raw_columns_for_profile("alpha8") == ALPHA_SOURCE_COLUMNS
    assert required_raw_columns_for_profile("alpha12") == ALPHA_SOURCE_COLUMNS
    assert required_raw_columns_for_profile("alpha16") == ALPHA_SOURCE_COLUMNS
    assert required_raw_columns_for_profile("alpha20") == ALPHA_SOURCE_COLUMNS
    residual_required = required_raw_columns_for_profile("residual")
    for name in ALPHA_SOURCE_COLUMNS:
        assert name in residual_required
    for name in RESIDUAL_CONTEXT_COLUMNS:
        assert name in residual_required
    assert required_raw_columns_for_profile("core20") == CORE20_FEATURE_COLUMNS
    assert required_raw_columns_for_profile("alpha4_from_core20") == CORE20_FEATURE_COLUMNS
    assert required_raw_columns_for_profile("alpha8_from_core20") == CORE20_FEATURE_COLUMNS


def test_apply_feature_profile_rejects_missing_required_columns() -> None:
    partial = pd.DataFrame(
        {
            "momentum_10_20": [0.1, 0.2],
            "breakout_20": [0.01, -0.02],
        }
    )
    with pytest.raises(ValueError, match="missing raw feature columns"):
        apply_feature_profile(partial, "alpha4")
