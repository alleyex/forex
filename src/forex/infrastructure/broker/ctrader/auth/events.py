"""
cTrader account/session payload constants.
"""
from __future__ import annotations

from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOAPayloadType


ACCOUNT_DISCONNECT_EVENT = ProtoOAPayloadType.PROTO_OA_ACCOUNT_DISCONNECT_EVENT
ACCOUNTS_TOKEN_INVALIDATED_EVENT = ProtoOAPayloadType.PROTO_OA_ACCOUNTS_TOKEN_INVALIDATED_EVENT

