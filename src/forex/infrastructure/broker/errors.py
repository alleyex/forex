from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ErrorCode(str, Enum):
    VALIDATION = "VALIDATION"
    TIMEOUT = "TIMEOUT"
    AUTH = "AUTH"
    NETWORK = "NETWORK"
    PROVIDER = "PROVIDER"


@dataclass(frozen=True)
class BrokerError:
    code: ErrorCode
    message: str
    detail: str | None = None

    def __str__(self) -> str:  # pragma: no cover - trivial
        detail = f" ({self.detail})" if self.detail else ""
        return f"[{self.code.value}] {self.message}{detail}"


def error_message(code: ErrorCode, message: str, detail: str | None = None) -> str:
    return str(BrokerError(code=code, message=message, detail=detail))
