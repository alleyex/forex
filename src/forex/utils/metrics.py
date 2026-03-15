from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger("metrics")

TagSet = frozenset[tuple[str, str]]


def _normalize_tags(tags: dict[str, str] | None = None) -> TagSet:
    if not tags:
        return frozenset()
    return frozenset((str(k), str(v)) for k, v in sorted(tags.items()))


@dataclass(frozen=True)
class MetricKey:
    name: str
    tags: TagSet


@dataclass
class Observation:
    count: int = 0
    total: float = 0.0
    minimum: float = 0.0
    maximum: float = 0.0

    def update(self, value: float) -> None:
        if self.count == 0:
            self.minimum = value
            self.maximum = value
        else:
            self.minimum = min(self.minimum, value)
            self.maximum = max(self.maximum, value)
        self.count += 1
        self.total += value

    @property
    def average(self) -> float:
        if self.count == 0:
            return 0.0
        return self.total / self.count


class MetricsRegistry:
    def __init__(self, *, log_interval_seconds: float | None = None) -> None:
        interval = log_interval_seconds
        if interval is None:
            interval = float(os.getenv("METRICS_LOG_INTERVAL", "60"))
        self._log_interval_seconds = max(0.0, interval)
        self._last_log_ts = 0.0
        self._counts: dict[MetricKey, int] = {}
        self._observations: dict[MetricKey, Observation] = {}

    def inc(self, name: str, value: int = 1, **tags: str) -> None:
        key = MetricKey(name, _normalize_tags(tags))
        self._counts[key] = self._counts.get(key, 0) + int(value)
        self._maybe_log()

    def observe(self, name: str, value: float, **tags: str) -> None:
        key = MetricKey(name, _normalize_tags(tags))
        obs = self._observations.get(key)
        if obs is None:
            obs = Observation()
            self._observations[key] = obs
        obs.update(float(value))
        self._maybe_log()

    def timer(self, name: str, **tags: str):
        return _Timer(self, name, tags)

    def snapshot(self) -> tuple[dict[str, int], dict[str, Observation]]:
        counts = {self._format_key(k): v for k, v in self._counts.items()}
        observations = {self._format_key(k): v for k, v in self._observations.items()}
        return counts, observations

    def _maybe_log(self) -> None:
        if self._log_interval_seconds <= 0:
            return
        now = time.monotonic()
        if now - self._last_log_ts < self._log_interval_seconds:
            return
        self._last_log_ts = now
        self._log_snapshot()

    def _log_snapshot(self) -> None:
        counts, observations = self.snapshot()
        if not counts and not observations:
            return
        lines = ["metrics snapshot"]
        for name, value in sorted(counts.items()):
            lines.append(f"count {name}={value}")
        for name, obs in sorted(observations.items()):
            lines.append(
                "observe "
                f"{name} count={obs.count} avg={obs.average:.4f} "
                f"min={obs.minimum:.4f} max={obs.maximum:.4f}"
            )
        logger.info(" | ".join(lines))

    @staticmethod
    def _format_key(key: MetricKey) -> str:
        if not key.tags:
            return key.name
        tag_text = ",".join(f"{k}={v}" for k, v in key.tags)
        return f"{key.name}{{{tag_text}}}"


class _Timer:
    def __init__(self, registry: MetricsRegistry, name: str, tags: dict[str, str]):
        self._registry = registry
        self._name = name
        self._tags = tags
        self._start: float | None = None

    def __enter__(self):
        self._start = time.monotonic()
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        if self._start is None:
            return
        duration = time.monotonic() - self._start
        self._registry.observe(self._name, duration, **self._tags)


metrics = MetricsRegistry()


def compute_sharpe_ratio_from_equity(equity_series: list[float] | np.ndarray) -> float:
    values = np.asarray(equity_series, dtype=np.float64)
    if values.size < 2:
        return 0.0
    prev = values[:-1]
    curr = values[1:]
    valid = prev > 0.0
    if not np.any(valid):
        return 0.0
    returns = (curr[valid] - prev[valid]) / prev[valid]
    if returns.size < 2:
        return 0.0
    std = float(np.std(returns))
    if std <= 1e-12:
        return 0.0
    return float(np.mean(returns) / std)
