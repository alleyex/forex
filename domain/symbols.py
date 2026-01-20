from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Symbol:
    symbol_id: int
    name: str
