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
