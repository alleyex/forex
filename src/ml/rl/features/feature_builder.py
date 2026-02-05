from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class FeatureSet:
    features: np.ndarray
    closes: np.ndarray
    timestamps: Sequence[str]
    names: list[str]


def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "utc_timestamp_minutes" in df.columns:
        df = df.sort_values("utc_timestamp_minutes")
    return df.reset_index(drop=True)


def build_features(df: pd.DataFrame) -> FeatureSet:
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    if "volume" in df.columns:
        volume = df["volume"].astype(float)
        vol_mean = volume.rolling(20).mean()
        vol_std = volume.rolling(20).std().replace(0, np.nan)
        vol_z = (volume - vol_mean) / vol_std
    else:
        vol_z = pd.Series(0.0, index=df.index)

    returns_1 = close.pct_change(1)
    returns_5 = close.pct_change(5)
    sma_10 = close.rolling(10).mean() / close - 1.0
    sma_20 = close.rolling(20).mean() / close - 1.0

    rsi_14 = _rsi(close, period=14)
    atr_14 = _atr(high, low, close, period=14) / close

    features = pd.DataFrame(
        {
            "returns_1": returns_1,
            "returns_5": returns_5,
            "sma_10": sma_10,
            "sma_20": sma_20,
            "rsi_14": rsi_14,
            "atr_14": atr_14,
            "vol_z": vol_z,
        }
    )

    valid = features.dropna().index
    features = features.loc[valid]
    closes = close.loc[valid]
    timestamps = df.loc[valid, "timestamp"].astype(str).tolist()

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
    return 100 - (100 / (1 + rs))


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
