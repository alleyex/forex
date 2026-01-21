"""
Shared helpers for spot subscription messages.
"""
from typing import Callable, Optional

from ctrader_open_api import Client
from ctrader_open_api.messages.OpenApiMessages_pb2 import (
    ProtoOASubscribeSpotsReq,
    ProtoOAUnsubscribeSpotsReq,
)


def send_spot_subscribe(
    client: Client,
    *,
    account_id: int,
    symbol_id: int,
    log: Optional[Callable[[str], None]] = None,
    subscribe_to_spot_timestamp: bool = True,
) -> None:
    request = ProtoOASubscribeSpotsReq()
    request.ctidTraderAccountId = account_id
    request.symbolId.append(symbol_id)
    request.subscribeToSpotTimestamp = subscribe_to_spot_timestamp
    client.send(request)
    if log:
        log(f"📡 已送出報價訂閱：{symbol_id}")


def send_spot_unsubscribe(
    client: Client,
    *,
    account_id: int,
    symbol_id: int,
    log: Optional[Callable[[str], None]] = None,
) -> None:
    request = ProtoOAUnsubscribeSpotsReq()
    request.ctidTraderAccountId = account_id
    request.symbolId.append(symbol_id)
    client.send(request)
    if log:
        log(f"🔕 已送出報價退訂：{symbol_id}")
