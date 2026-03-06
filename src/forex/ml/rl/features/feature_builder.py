from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import json

import numpy as np
import pandas as pd

ALPHA_FEATURE_COLUMNS: tuple[str, ...] = (
    "trend_score",
    "range_score",
    "breakout_score",
    "volatility_score",
)
ALPHA_SOURCE_COLUMNS: tuple[str, ...] = (
    "momentum_10_20",
    "momentum_20_50",
    "momentum_50_100",
    "trend_flag_25",
    "range_strength_10_50_atr14",
    "rsi_14",
    "breakout_20",
    "breakout_50",
    "atr_14",
    "vol_ratio_10_50",
    "vol_pct_72_252",
    "bollinger_band_width_20",
)
RESIDUAL_CONTEXT_COLUMNS: tuple[str, ...] = (
    "atr_14",
    "vol_pct_72_252",
    "is_london_session",
    "is_ny_session",
    "is_london_ny_overlap",
    "since_london_open_return",
    "since_ny_open_return",
    "ny_open_gap_prev_close",
)


ALL_FEATURE_COLUMNS: tuple[str, ...] = (
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
    "breakout_20",
    "breakout_50",
    "rsi_14",
    "atr_14",
    "atr_ratio_14_50",
    "atr_ratio_14_100",
    "vol_ratio_10_50",
    "vol_pct_72_252",
    "bollinger_band_width_20",
    "distance_to_rolling_high_20",
    "distance_to_rolling_low_20",
    "body_size_ratio",
    "close_location_in_bar",
    "adx_14",
    "trend_flag_25",
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
)


@dataclass(frozen=True)
class FeatureSet:
    features: np.ndarray
    closes: np.ndarray
    timestamps: Sequence[str]
    names: list[str]


@dataclass(frozen=True)
class FeatureScaler:
    means: np.ndarray
    stds: np.ndarray
    names: list[str]


def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "utc_timestamp_minutes" in df.columns:
        df = df.sort_values("utc_timestamp_minutes")
    return df.reset_index(drop=True)


def select_feature_columns(features: pd.DataFrame, selected_names: Sequence[str]) -> pd.DataFrame:
    names = [str(name).strip() for name in selected_names if str(name).strip()]
    if not names:
        raise ValueError("Feature subset must contain at least one feature name.")
    missing = [name for name in names if name not in features.columns]
    if missing:
        raise ValueError(f"Feature subset references unknown columns: {', '.join(missing)}")
    return features.loc[:, names].copy()


def infer_feature_profile_from_names(feature_names: Sequence[str]) -> str:
    names = {str(name).strip() for name in feature_names if str(name).strip()}
    if not names:
        return "raw53"
    alpha_names = set(ALPHA_FEATURE_COLUMNS)
    residual_names = alpha_names | set(RESIDUAL_CONTEXT_COLUMNS)
    if names.issubset(alpha_names):
        return "alpha4"
    if alpha_names.issubset(names) and names.issubset(residual_names):
        return "residual"
    return "raw53"


def apply_feature_profile(features: pd.DataFrame, profile: str) -> pd.DataFrame:
    profile_name = str(profile).strip().lower() or "raw53"
    if profile_name == "raw53":
        return features.copy()
    required = required_raw_columns_for_profile(profile_name)
    missing = [name for name in required if name not in features.columns]
    if missing:
        raise ValueError(
            "Feature profile requires missing raw feature columns: "
            + ", ".join(missing)
        )
    alpha_frame = _build_alpha_layer(features)
    if profile_name == "alpha4":
        return alpha_frame
    if profile_name == "residual":
        residual = alpha_frame.copy()
        for name in RESIDUAL_CONTEXT_COLUMNS:
            if name in features.columns:
                residual[name] = pd.to_numeric(features[name], errors="coerce").fillna(0.0).astype(float)
        ordered = [*ALPHA_FEATURE_COLUMNS, *[name for name in RESIDUAL_CONTEXT_COLUMNS if name in residual.columns]]
        return residual.loc[:, ordered].copy()
    raise ValueError(f"Unknown feature profile: {profile}")


def required_raw_columns_for_profile(profile: str) -> tuple[str, ...]:
    profile_name = str(profile).strip().lower() or "raw53"
    if profile_name == "raw53":
        return tuple()
    if profile_name == "alpha4":
        return ALPHA_SOURCE_COLUMNS
    if profile_name == "residual":
        return (*ALPHA_SOURCE_COLUMNS, *RESIDUAL_CONTEXT_COLUMNS)
    raise ValueError(f"Unknown feature profile: {profile}")


def filter_feature_rows_by_session(
    features: pd.DataFrame,
    closes: pd.Series,
    timestamps: Sequence[str],
    session_filter: str,
) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    session_name = str(session_filter).strip().lower() or "all"
    column_map = {
        "all": None,
        "monday_open": "is_monday_open_window",
        "london": "is_london_session",
        "ny": "is_ny_session",
        "overlap": "is_london_ny_overlap",
    }
    if session_name not in column_map:
        raise ValueError(f"Unknown session filter: {session_filter}")
    column_name = column_map[session_name]
    if column_name is None:
        return features.copy(), closes.copy(), list(timestamps)
    if column_name not in features.columns:
        raise ValueError(f"Session filter requires feature column: {column_name}")
    mask = features[column_name].astype(float) > 0.5
    filtered_features = features.loc[mask].copy()
    filtered_closes = closes.loc[mask].copy()
    timestamp_series = pd.Series(list(timestamps), index=features.index, dtype=object)
    filtered_timestamps = timestamp_series.loc[mask].astype(str).tolist()
    return filtered_features, filtered_closes, filtered_timestamps


def build_feature_frame(
    df: pd.DataFrame,
    selected_names: Sequence[str] | None = None,
) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    if selected_names is None:
        selected_order = list(ALL_FEATURE_COLUMNS)
    else:
        selected_order = [str(name).strip() for name in selected_names if str(name).strip()]
        if not selected_order:
            raise ValueError("Feature subset must contain at least one feature name.")
        unknown = [name for name in selected_order if name not in ALL_FEATURE_COLUMNS]
        if unknown:
            raise ValueError(f"Feature subset references unknown columns: {', '.join(unknown)}")
    requested = set(selected_order)

    def wants(*names: str) -> bool:
        return any(name in requested for name in names)

    open_ = df["open"].astype(float)
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    datetimes = _parse_datetimes(df)
    timestamp_text = _timestamp_strings(df, datetimes)
    features_dict: dict[str, pd.Series] = {}

    if wants("vol_z") and "volume" in df.columns:
        volume = df["volume"].astype(float)
        vol_mean = volume.rolling(20).mean()
        vol_std = volume.rolling(20).std().replace(0, np.nan)
        vol_z = (volume - vol_mean) / vol_std
        features_dict["vol_z"] = vol_z
    elif wants("vol_z"):
        features_dict["vol_z"] = pd.Series(0.0, index=df.index)

    returns_1 = close.pct_change(1) if wants(
        "returns_1",
        "vol_ratio_10_50",
        "vol_pct_72_252",
        "bollinger_band_width_20",
    ) else None
    if "returns_1" in requested:
        features_dict["returns_1"] = returns_1
    returns_5 = close.pct_change(5) if "returns_5" in requested else None
    if returns_5 is not None:
        features_dict["returns_5"] = returns_5
    returns_10 = close.pct_change(10) if "returns_10" in requested else None
    if returns_10 is not None:
        features_dict["returns_10"] = returns_10
    returns_20 = close.pct_change(20) if "returns_20" in requested else None
    if returns_20 is not None:
        features_dict["returns_20"] = returns_20
    returns_60 = close.pct_change(60) if "returns_60" in requested else None
    if returns_60 is not None:
        features_dict["returns_60"] = returns_60

    sma_10 = close.rolling(10).mean() / close - 1.0 if wants("sma_10", "range_strength_10_50_atr14") else None
    if "sma_10" in requested:
        features_dict["sma_10"] = sma_10
    sma_20 = close.rolling(20).mean() / close - 1.0 if "sma_20" in requested else None
    if sma_20 is not None:
        features_dict["sma_20"] = sma_20
    sma_50 = close.rolling(50).mean() / close - 1.0 if wants("sma_50", "range_strength_10_50_atr14") else None
    if "sma_50" in requested:
        features_dict["sma_50"] = sma_50
    if "momentum_10_20" in requested:
        features_dict["momentum_10_20"] = close.rolling(10).mean() / close.rolling(20).mean() - 1.0
    if "momentum_20_50" in requested:
        features_dict["momentum_20_50"] = close.rolling(20).mean() / close.rolling(50).mean() - 1.0
    if "momentum_50_100" in requested:
        features_dict["momentum_50_100"] = close.rolling(50).mean() / close.rolling(100).mean() - 1.0
    if "price_z_20" in requested:
        features_dict["price_z_20"] = _rolling_zscore(close, 20)
    if "price_z_50" in requested:
        features_dict["price_z_50"] = _rolling_zscore(close, 50)
    if "price_z_100" in requested:
        features_dict["price_z_100"] = _rolling_zscore(close, 100)
    if "breakout_20" in requested:
        features_dict["breakout_20"] = close / high.shift(1).rolling(20).max() - 1.0
    if "breakout_50" in requested:
        features_dict["breakout_50"] = close / high.shift(1).rolling(50).max() - 1.0
    if "rsi_14" in requested:
        features_dict["rsi_14"] = _rsi(close, period=14)

    atr_14 = _atr(high, low, close, period=14) / close if wants(
        "atr_14",
        "atr_ratio_14_50",
        "atr_ratio_14_100",
        "range_strength_10_50_atr14",
    ) else None
    if "atr_14" in requested:
        features_dict["atr_14"] = atr_14
    if wants("atr_ratio_14_50"):
        atr_50 = _atr(high, low, close, period=50) / close
        features_dict["atr_ratio_14_50"] = atr_14 / atr_50.replace(0, np.nan)
    if wants("atr_ratio_14_100"):
        atr_100 = _atr(high, low, close, period=100) / close
        features_dict["atr_ratio_14_100"] = atr_14 / atr_100.replace(0, np.nan)

    if wants("vol_ratio_10_50", "bollinger_band_width_20", "vol_pct_72_252"):
        assert returns_1 is not None
    if "vol_ratio_10_50" in requested:
        rolling_std_10 = returns_1.rolling(10).std()
        rolling_std_50 = returns_1.rolling(50).std()
        features_dict["vol_ratio_10_50"] = rolling_std_10 / rolling_std_50.replace(0, np.nan)
    if "vol_pct_72_252" in requested:
        rolling_std_72 = returns_1.rolling(72).std()
        features_dict["vol_pct_72_252"] = _rolling_percentile_rank(rolling_std_72, 252)
    if "bollinger_band_width_20" in requested:
        rolling_std_20 = returns_1.rolling(20).std()
        features_dict["bollinger_band_width_20"] = (4.0 * rolling_std_20) / close.replace(0, np.nan)

    if "distance_to_rolling_high_20" in requested:
        rolling_high_20 = high.rolling(20).max()
        features_dict["distance_to_rolling_high_20"] = close / rolling_high_20.replace(0, np.nan) - 1.0
    if "distance_to_rolling_low_20" in requested:
        rolling_low_20 = low.rolling(20).min()
        features_dict["distance_to_rolling_low_20"] = close / rolling_low_20.replace(0, np.nan) - 1.0
    if wants("body_size_ratio", "close_location_in_bar"):
        bar_range = (high - low).replace(0, np.nan)
        if "body_size_ratio" in requested:
            features_dict["body_size_ratio"] = (close - open_).abs() / bar_range
        if "close_location_in_bar" in requested:
            features_dict["close_location_in_bar"] = (close - low) / bar_range

    adx_14 = _adx(high, low, close, period=14) if wants("adx_14", "trend_flag_25") else None
    if "adx_14" in requested:
        features_dict["adx_14"] = adx_14
    if "trend_flag_25" in requested:
        features_dict["trend_flag_25"] = (adx_14 > 25.0).astype(float)
    if "range_strength_10_50_atr14" in requested:
        trend_distance_atr = (sma_10 - sma_50).abs() / (atr_14 + 1e-8)
        features_dict["range_strength_10_50_atr14"] = 1.0 / (1.0 + trend_distance_atr)

    time_feature_names = {
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
    session_context_names = {
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
    }
    if requested.intersection(time_feature_names | session_context_names):
        (
            hour_sin,
            hour_cos,
            weekday_sin,
            weekday_cos,
            minute_of_week_sin,
            minute_of_week_cos,
            is_monday_open_window,
            is_london_session,
            is_ny_session,
            is_london_ny_overlap,
        ) = _time_features(datetimes)
        time_features = {
            "hour_sin": hour_sin,
            "hour_cos": hour_cos,
            "weekday_sin": weekday_sin,
            "weekday_cos": weekday_cos,
            "minute_of_week_sin": minute_of_week_sin,
            "minute_of_week_cos": minute_of_week_cos,
            "is_monday_open_window": is_monday_open_window,
            "is_london_session": is_london_session,
            "is_ny_session": is_ny_session,
            "is_london_ny_overlap": is_london_ny_overlap,
        }
        for name in time_feature_names.intersection(requested):
            features_dict[name] = time_features[name]

        if requested.intersection(session_context_names):
            session_features = _session_context_features(
                datetimes=datetimes,
                open_=open_,
                close=close,
                high=high,
                low=low,
                is_london_session=is_london_session,
                is_ny_session=is_ny_session,
            )
            for name, series in zip(
                (
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
                ),
                session_features,
            ):
                if name in requested:
                    features_dict[name] = series

    features = pd.DataFrame({name: features_dict[name] for name in selected_order})

    valid = features.dropna().index
    features = features.loc[valid]
    closes = close.loc[valid]
    timestamps = timestamp_text.loc[valid].astype(str).tolist()

    return features, closes, timestamps


def fit_scaler(features: pd.DataFrame) -> FeatureScaler:
    means = features.mean()
    stds = features.std().replace(0, np.nan)
    return FeatureScaler(
        means=means.to_numpy(dtype=np.float32),
        stds=stds.to_numpy(dtype=np.float32),
        names=list(features.columns),
    )


def apply_scaler(features: pd.DataFrame, scaler: FeatureScaler) -> pd.DataFrame:
    aligned = features[scaler.names]
    values = (aligned.to_numpy(dtype=np.float32) - scaler.means) / scaler.stds
    values = np.nan_to_num(values, nan=0.0, posinf=0.0, neginf=0.0)
    return pd.DataFrame(values, columns=scaler.names, index=aligned.index)


def save_scaler(scaler: FeatureScaler, path: str | Path) -> None:
    payload = {
        "names": list(scaler.names),
        "means": scaler.means.tolist(),
        "stds": scaler.stds.tolist(),
    }
    Path(path).write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def load_scaler(path: str | Path) -> FeatureScaler:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    names = list(data.get("names", []))
    means = np.array(data.get("means", []), dtype=np.float32)
    stds = np.array(data.get("stds", []), dtype=np.float32)
    return FeatureScaler(means=means, stds=stds, names=names)


def build_features(
    df: pd.DataFrame,
    *,
    scaler: FeatureScaler | None = None,
    normalize: bool = False,
) -> FeatureSet:
    features, closes, timestamps = build_feature_frame(df)
    if scaler is not None:
        inferred_profile = infer_feature_profile_from_names(scaler.names)
        features = apply_feature_profile(features, inferred_profile)
        features = apply_scaler(features, scaler)
    elif normalize:
        features = apply_scaler(features, fit_scaler(features))

    return FeatureSet(
        features=features.to_numpy(dtype=np.float32),
        closes=closes.to_numpy(dtype=np.float32),
        timestamps=timestamps,
        names=list(features.columns),
    )


def _build_alpha_layer(features: pd.DataFrame) -> pd.DataFrame:
    def g(name: str, default: float = 0.0) -> pd.Series:
        if name not in features.columns:
            return pd.Series(default, index=features.index, dtype=float)
        return pd.to_numeric(features[name], errors="coerce").fillna(default).astype(float)

    momentum_fast = g("momentum_10_20")
    momentum_mid = g("momentum_20_50")
    momentum_slow = g("momentum_50_100")
    trend_flag = g("trend_flag_25")
    range_strength = g("range_strength_10_50_atr14")
    rsi = g("rsi_14", 50.0).clip(0.0, 100.0)
    breakout_fast = g("breakout_20")
    breakout_slow = g("breakout_50")
    atr_14 = g("atr_14")
    vol_ratio = g("vol_ratio_10_50")
    vol_pct = g("vol_pct_72_252", 0.5).clip(0.0, 1.0)
    boll_width = g("bollinger_band_width_20")

    trend_core = (0.45 * momentum_fast) + (0.35 * momentum_mid) + (0.20 * momentum_slow)
    trend_score = np.tanh((8.0 * trend_core) + (1.5 * trend_flag * (1.0 - range_strength)))

    rsi_neutral = 1.0 - ((rsi - 50.0).abs() / 50.0)
    breakout_compression = 1.0 / (1.0 + breakout_fast.abs() + breakout_slow.abs())
    range_raw = (0.60 * range_strength) + (0.30 * rsi_neutral) + (0.10 * breakout_compression)
    range_score = np.clip((2.0 * range_raw) - 1.0, -1.0, 1.0)

    breakout_core = (0.60 * breakout_fast) + (0.40 * breakout_slow)
    breakout_score = np.tanh(6.0 * breakout_core)

    vol_core = (0.50 * atr_14) + (0.25 * vol_ratio) + (0.25 * boll_width)
    volatility_score = np.tanh((2.0 * vol_core) + (1.2 * (vol_pct - 0.5)))

    alpha = pd.DataFrame(
        {
            "trend_score": trend_score.astype(float),
            "range_score": range_score.astype(float),
            "breakout_score": breakout_score.astype(float),
            "volatility_score": volatility_score.astype(float),
        },
        index=features.index,
    )
    return alpha.replace([np.inf, -np.inf], np.nan).fillna(0.0)


def _rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    zero_gain = gain <= 1e-12
    zero_loss = loss <= 1e-12
    both_zero = zero_gain & zero_loss
    rsi = rsi.mask(zero_loss & ~zero_gain, 100.0)
    rsi = rsi.mask(zero_gain & ~zero_loss, 0.0)
    rsi = rsi.mask(both_zero, 50.0)
    return rsi


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    prev_close = close.shift(1)
    ranges = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    )
    true_range = ranges.max(axis=1)
    return true_range.rolling(period).mean()


def _rolling_zscore(series: pd.Series, period: int) -> pd.Series:
    mean = series.rolling(period).mean()
    std = series.rolling(period).std().replace(0, np.nan)
    return (series - mean) / std


def _rolling_percentile_rank(series: pd.Series, window: int) -> pd.Series:
    def _rank_last(values: np.ndarray) -> float:
        if len(values) == 0 or np.isnan(values[-1]):
            return np.nan
        valid = values[~np.isnan(values)]
        if len(valid) == 0:
            return np.nan
        return float(np.mean(valid <= values[-1]))

    min_periods = min(int(window), 64)
    return series.rolling(window, min_periods=min_periods).apply(_rank_last, raw=True)


def _adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    tr = _atr(high, low, close, period=1)
    tr_n = tr.rolling(period).mean().replace(0, np.nan)
    plus_di = 100.0 * plus_dm.rolling(period).mean() / tr_n
    minus_di = 100.0 * minus_dm.rolling(period).mean() / tr_n
    dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)) * 100.0
    return dx.rolling(period).mean()


def _parse_datetimes(df: pd.DataFrame) -> pd.Series:
    if "timestamp" in df.columns:
        parsed = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
        if parsed.notna().any():
            return parsed
    if "utc_timestamp_minutes" in df.columns:
        return pd.to_datetime(df["utc_timestamp_minutes"], unit="m", errors="coerce", utc=True)
    return pd.Series(pd.NaT, index=df.index)


def _timestamp_strings(df: pd.DataFrame, datetimes: pd.Series) -> pd.Series:
    if "timestamp" in df.columns:
        return df["timestamp"].astype(str)
    if datetimes.notna().any():
        return datetimes.dt.strftime("%Y-%m-%d %H:%M:%S%z").fillna("")
    return pd.Series("", index=df.index, dtype=str)


def _time_features(
    datetimes: pd.Series,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series, pd.Series, pd.Series, pd.Series, pd.Series, pd.Series, pd.Series]:
    hours = datetimes.dt.hour.fillna(0).astype(float) + datetimes.dt.minute.fillna(0).astype(float) / 60.0
    weekdays = datetimes.dt.dayofweek.fillna(0).astype(float)
    minutes_of_week = weekdays * 24.0 * 60.0 + datetimes.dt.hour.fillna(0).astype(float) * 60.0 + datetimes.dt.minute.fillna(0).astype(float)
    london = datetimes.dt.tz_convert("Europe/London")
    new_york = datetimes.dt.tz_convert("America/New_York")
    london_hours = london.dt.hour.fillna(0).astype(float) + london.dt.minute.fillna(0).astype(float) / 60.0
    new_york_hours = new_york.dt.hour.fillna(0).astype(float) + new_york.dt.minute.fillna(0).astype(float) / 60.0

    hour_angle = 2.0 * np.pi * hours / 24.0
    weekday_angle = 2.0 * np.pi * weekdays / 7.0
    week_angle = 2.0 * np.pi * minutes_of_week / (7.0 * 24.0 * 60.0)

    is_monday_open_window = ((weekdays == 0.0) & (hours < 3.0)).astype(float)
    is_london_session = ((london_hours >= 8.0) & (london_hours < 17.0)).astype(float)
    is_ny_session = ((new_york_hours >= 8.0) & (new_york_hours < 17.0)).astype(float)
    is_london_ny_overlap = (
        ((london_hours >= 8.0) & (london_hours < 17.0))
        & ((new_york_hours >= 8.0) & (new_york_hours < 17.0))
    ).astype(float)

    hour_sin = pd.Series(np.sin(hour_angle), index=datetimes.index)
    hour_cos = pd.Series(np.cos(hour_angle), index=datetimes.index)
    weekday_sin = pd.Series(np.sin(weekday_angle), index=datetimes.index)
    weekday_cos = pd.Series(np.cos(weekday_angle), index=datetimes.index)
    minute_of_week_sin = pd.Series(np.sin(week_angle), index=datetimes.index)
    minute_of_week_cos = pd.Series(np.cos(week_angle), index=datetimes.index)
    return (
        hour_sin,
        hour_cos,
        weekday_sin,
        weekday_cos,
        minute_of_week_sin,
        minute_of_week_cos,
        pd.Series(is_monday_open_window, index=datetimes.index),
        pd.Series(is_london_session, index=datetimes.index),
        pd.Series(is_ny_session, index=datetimes.index),
        pd.Series(is_london_ny_overlap, index=datetimes.index),
    )


def _session_context_features(
    *,
    datetimes: pd.Series,
    open_: pd.Series,
    close: pd.Series,
    high: pd.Series,
    low: pd.Series,
    is_london_session: pd.Series,
    is_ny_session: pd.Series,
) -> tuple[
    pd.Series,
    pd.Series,
    pd.Series,
    pd.Series,
    pd.Series,
    pd.Series,
    pd.Series,
    pd.Series,
    pd.Series,
    pd.Series,
    pd.Series,
    pd.Series,
]:
    if not datetimes.notna().any():
        zeros = pd.Series(0.0, index=close.index, dtype=float)
        return (zeros, zeros, zeros, zeros, zeros, zeros, zeros, zeros, zeros, zeros, zeros, zeros)

    new_york = datetimes.dt.tz_convert("America/New_York")
    london = datetimes.dt.tz_convert("Europe/London")
    ny_dates = new_york.dt.strftime("%Y-%m-%d").fillna("")
    london_dates = london.dt.strftime("%Y-%m-%d").fillna("")

    daily = pd.DataFrame(
        {
            "ny_date": ny_dates,
            "open": open_,
            "close": close,
            "high": high,
            "low": low,
        }
    )
    daily_summary = daily.groupby("ny_date", sort=False).agg(
        day_open=("open", "first"),
        day_close=("close", "last"),
        day_high=("high", "max"),
        day_low=("low", "min"),
    )
    prev_summary = daily_summary.shift(1)
    prev_day_open = ny_dates.map(prev_summary["day_open"])
    prev_day_close = ny_dates.map(prev_summary["day_close"])
    prev_day_high = ny_dates.map(prev_summary["day_high"])
    prev_day_low = ny_dates.map(prev_summary["day_low"])
    prev_day_return = prev_day_close / prev_day_open.replace(0, np.nan) - 1.0
    prev_day_range_pct = (prev_day_high - prev_day_low) / prev_day_close.replace(0, np.nan)
    prev_day_range = (prev_day_high - prev_day_low).replace(0, np.nan)
    prev_day_range_position = (close - prev_day_low) / prev_day_range
    distance_to_prev_day_high = close / prev_day_high.replace(0, np.nan) - 1.0
    distance_to_prev_day_low = close / prev_day_low.replace(0, np.nan) - 1.0

    day_high_so_far = high.groupby(ny_dates, sort=False).cummax()
    day_low_so_far = low.groupby(ny_dates, sort=False).cummin()
    distance_to_day_high_so_far = close / day_high_so_far.replace(0, np.nan) - 1.0
    distance_to_day_low_so_far = close / day_low_so_far.replace(0, np.nan) - 1.0

    london_start_close = close.where(is_london_session > 0.5).groupby(london_dates, sort=False).transform("first")
    ny_start_close = close.where(is_ny_session > 0.5).groupby(ny_dates, sort=False).transform("first")
    ny_open_gap_prev_close = ny_start_close / prev_day_close.replace(0, np.nan) - 1.0
    london_to_ny_open_return = ny_start_close / london_start_close.replace(0, np.nan) - 1.0
    london_after_open = london.dt.hour.fillna(0).astype(float) >= 8.0
    ny_after_open = new_york.dt.hour.fillna(0).astype(float) >= 8.0
    since_london_open_return = (close / london_start_close.replace(0, np.nan) - 1.0).where(
        london_after_open & london_start_close.notna(),
        0.0,
    )
    since_ny_open_return = (close / ny_start_close.replace(0, np.nan) - 1.0).where(
        ny_after_open & ny_start_close.notna(),
        0.0,
    )
    range_centered = (prev_day_range_position - 0.5).clip(-2.0, 2.0)
    ny_reversal_pressure = london_to_ny_open_return * range_centered

    return tuple(
        series.astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        for series in (
            prev_day_return,
            prev_day_range_pct,
            prev_day_range_position,
            distance_to_prev_day_high,
            distance_to_prev_day_low,
            distance_to_day_high_so_far,
            distance_to_day_low_so_far,
            since_london_open_return,
            since_ny_open_return,
            ny_open_gap_prev_close,
            london_to_ny_open_return,
            ny_reversal_pressure,
        )
    )
