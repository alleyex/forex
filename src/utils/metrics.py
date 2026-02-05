from __future__ import annotations

import os
import time
import logging
from dataclasses import dataclass
from typing import Dict, FrozenSet, Iterable, Optional, Tuple

logger = logging.getLogger("metrics")

TagSet = FrozenSet[Tuple[str, str]]


def _normalize_tags(tags: Optional[dict[str, str]] = None) -> TagSet:
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
    def __init__(self, *, log_interval_seconds: Optional[float] = None) -> None:
        interval = log_interval_seconds
        if interval is None:
            interval = float(os.getenv("METRICS_LOG_INTERVAL", "60"))
        self._log_interval_seconds = max(0.0, interval)
        self._last_log_ts = 0.0
        self._counts: Dict[MetricKey, int] = {}
        self._observations: Dict[MetricKey, Observation] = {}

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
                f"observe {name} count={obs.count} avg={obs.average:.4f} min={obs.minimum:.4f} max={obs.maximum:.4f}"
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
        self._start: Optional[float] = None

    def __enter__(self):
        self._start = time.monotonic()
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._start is None:
            return
        duration = time.monotonic() - self._start
        self._registry.observe(self._name, duration, **self._tags)


metrics = MetricsRegistry()
