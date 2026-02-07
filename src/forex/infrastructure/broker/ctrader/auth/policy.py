"""
cTrader auth error policy helpers.
"""
from __future__ import annotations

from forex.infrastructure.broker.ctrader.auth.errors import CTraderErrorCode


INVALID_TOKEN_ERROR_CODES = {
    int(CTraderErrorCode.OA_AUTH_TOKEN_EXPIRED),
    int(CTraderErrorCode.ACCOUNT_NOT_AUTHORIZED),
    int(CTraderErrorCode.CH_ACCESS_TOKEN_INVALID),
}


def is_invalid_token_error(code: object) -> bool:
    try:
        return int(code) in INVALID_TOKEN_ERROR_CODES
    except (TypeError, ValueError):
        return False

