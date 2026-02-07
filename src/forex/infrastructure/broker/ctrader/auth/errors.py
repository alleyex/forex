"""
cTrader Open API error code mapping.
"""
from __future__ import annotations

from enum import IntEnum
from typing import Optional


class CTraderErrorCode(IntEnum):
    OA_AUTH_TOKEN_EXPIRED = 1
    ACCOUNT_NOT_AUTHORIZED = 2
    CH_CLIENT_AUTH_FAILURE = 101
    CH_CLIENT_NOT_AUTHENTICATED = 102
    CH_CLIENT_ALREADY_AUTHENTICATED = 103
    CH_ACCESS_TOKEN_INVALID = 104


_ERROR_CODE_NAMES = {
    int(CTraderErrorCode.OA_AUTH_TOKEN_EXPIRED): "OA_AUTH_TOKEN_EXPIRED",
    int(CTraderErrorCode.ACCOUNT_NOT_AUTHORIZED): "ACCOUNT_NOT_AUTHORIZED",
    int(CTraderErrorCode.CH_CLIENT_AUTH_FAILURE): "CH_CLIENT_AUTH_FAILURE",
    int(CTraderErrorCode.CH_CLIENT_NOT_AUTHENTICATED): "CH_CLIENT_NOT_AUTHENTICATED",
    int(CTraderErrorCode.CH_CLIENT_ALREADY_AUTHENTICATED): "CH_CLIENT_ALREADY_AUTHENTICATED",
    int(CTraderErrorCode.CH_ACCESS_TOKEN_INVALID): "CH_ACCESS_TOKEN_INVALID",
}


def describe_error_code(code: object) -> Optional[str]:
    try:
        return _ERROR_CODE_NAMES.get(int(code))
    except (TypeError, ValueError):
        return None

