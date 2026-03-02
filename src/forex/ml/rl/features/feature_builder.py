from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import json

import numpy as np
import pandas as pd


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


def build_feature_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    datetimes = _parse_datetimes(df)
    timestamp_text = _timestamp_strings(df, datetimes)
    if "volume" in df.columns:
        volume = df["volume"].astype(float)
        vol_mean = volume.rolling(20).mean()
        vol_std = volume.rolling(20).std().replace(0, np.nan)
        vol_z = (volume - vol_mean) / vol_std
    else:
        vol_z = pd.Series(0.0, index=df.index)

    returns_1 = close.pct_change(1)
    returns_5 = close.pct_change(5)
    returns_10 = close.pct_change(10)
    returns_20 = close.pct_change(20)
    sma_10 = close.rolling(10).mean() / close - 1.0
    sma_20 = close.rolling(20).mean() / close - 1.0
    sma_50 = close.rolling(50).mean() / close - 1.0
    momentum_10_20 = close.rolling(10).mean() / close.rolling(20).mean() - 1.0
    momentum_20_50 = close.rolling(20).mean() / close.rolling(50).mean() - 1.0
    rolling_std_10 = returns_1.rolling(10).std()
    rolling_std_20 = returns_1.rolling(20).std()
    rolling_std_50 = returns_1.rolling(50).std()
    rolling_std_100 = returns_1.rolling(100).std()
    price_z_20 = _rolling_zscore(close, 20)
    price_z_50 = _rolling_zscore(close, 50)
    price_z_100 = _rolling_zscore(close, 100)
    # Compare against the prior rolling high so breakout features are not
    # duplicates of the current-bar distance-to-high features below.
    breakout_20 = close / high.shift(1).rolling(20).max() - 1.0
    breakout_50 = close / high.shift(1).rolling(50).max() - 1.0

    rsi_14 = _rsi(close, period=14)
    atr_14 = _atr(high, low, close, period=14) / close
    atr_50 = _atr(high, low, close, period=50) / close
    atr_100 = _atr(high, low, close, period=100) / close
    atr_ratio_14_50 = atr_14 / atr_50.replace(0, np.nan)
    atr_ratio_14_100 = atr_14 / atr_100.replace(0, np.nan)
    vol_ratio_10_50 = rolling_std_10 / rolling_std_50.replace(0, np.nan)
    bollinger_band_width_20 = (4.0 * rolling_std_20) / close.replace(0, np.nan)
    rolling_high_20 = high.rolling(20).max()
    rolling_low_20 = low.rolling(20).min()
    distance_to_rolling_high_20 = close / rolling_high_20.replace(0, np.nan) - 1.0
    distance_to_rolling_low_20 = close / rolling_low_20.replace(0, np.nan) - 1.0
    bar_range = (high - low).replace(0, np.nan)
    body_size_ratio = (close - df["open"].astype(float)).abs() / bar_range
    close_location_in_bar = (close - low) / bar_range
    adx_14 = _adx(high, low, close, period=14)
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

    features = pd.DataFrame(
        {
            "returns_1": returns_1,
            "returns_5": returns_5,
            "returns_10": returns_10,
            "returns_20": returns_20,
            "sma_10": sma_10,
            "sma_20": sma_20,
            "sma_50": sma_50,
            "momentum_10_20": momentum_10_20,
            "momentum_20_50": momentum_20_50,
            "price_z_20": price_z_20,
            "price_z_50": price_z_50,
            "price_z_100": price_z_100,
            "breakout_20": breakout_20,
            "breakout_50": breakout_50,
            "rsi_14": rsi_14,
            "atr_14": atr_14,
            "atr_ratio_14_50": atr_ratio_14_50,
            "atr_ratio_14_100": atr_ratio_14_100,
            "vol_ratio_10_50": vol_ratio_10_50,
            "bollinger_band_width_20": bollinger_band_width_20,
            "distance_to_rolling_high_20": distance_to_rolling_high_20,
            "distance_to_rolling_low_20": distance_to_rolling_low_20,
            "body_size_ratio": body_size_ratio,
            "close_location_in_bar": close_location_in_bar,
            "adx_14": adx_14,
            "vol_z": vol_z,
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
    )

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
        features = apply_scaler(features, scaler)
    elif normalize:
        features = apply_scaler(features, fit_scaler(features))

    return FeatureSet(
        features=features.to_numpy(dtype=np.float32),
        closes=closes.to_numpy(dtype=np.float32),
        timestamps=timestamps,
        names=list(features.columns),
    )


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
