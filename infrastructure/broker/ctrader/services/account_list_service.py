"""
帳戶列表服務
"""
from dataclasses import dataclass
import threading
from typing import Callable, Optional, Protocol, Sequence

from ctrader_open_api import Client
from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAGetAccountListByAccessTokenReq
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOAPayloadType

from broker.base import BaseCallbacks, LogHistoryMixin, OperationStateMixin, build_callbacks
from infrastructure.broker.ctrader.services.app_auth_service import AppAuthService


class AccountInfoMessage(Protocol):
    ctidTraderAccountId: int
    isLive: bool
    traderLogin: Optional[int]


class AccountListMessage(Protocol):
    payloadType: int
    errorCode: int
    description: str
    ctidTraderAccount: Sequence[AccountInfoMessage]


@dataclass
class AccountListServiceCallbacks(BaseCallbacks):
    """AccountListService 的回調函式"""
    on_accounts_received: Optional[Callable[[list], None]] = None


class AccountListService(LogHistoryMixin[AccountListServiceCallbacks], OperationStateMixin):
    """
    透過存取權杖取得帳戶列表

    使用方式：
        service = AccountListService(app_auth_service, access_token)
        service.set_callbacks(on_accounts_received=..., on_error=...)
        service.fetch()
    """

    def __init__(self, app_auth_service: AppAuthService, access_token: str):
        self._app_auth_service = app_auth_service
        self._access_token = access_token
        self._callbacks = AccountListServiceCallbacks()
        self._in_progress = False
        self._timeout_timer: Optional[threading.Timer] = None
        self._log_history = []

    def set_access_token(self, access_token: str) -> None:
        self._access_token = access_token

    def set_callbacks(
        self,
        on_accounts_received: Optional[Callable[[list], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> None:
        """設定回調函式"""
        self._callbacks = build_callbacks(
            AccountListServiceCallbacks,
            on_accounts_received=on_accounts_received,
            on_error=on_error,
            on_log=on_log,
        )
        self._replay_log_history()

    def fetch(self, timeout_seconds: Optional[int] = None) -> None:
        """取得帳戶列表"""
        if not self._access_token:
            self._emit_error("缺少存取權杖")
            return

        if not self._start_operation():
            return

        self._app_auth_service.add_message_handler(self._handle_message)
        self._start_timeout_timer(timeout_seconds)
        self._send_request()

    def _send_request(self) -> None:
        """發送帳戶列表請求"""
        request = ProtoOAGetAccountListByAccessTokenReq()
        request.accessToken = self._access_token
        self._log("📥 正在取得帳戶列表...")
        try:
            client = self._app_auth_service.get_client()
        except Exception as exc:
            self._emit_error(str(exc))
            self._end_operation()
            self._app_auth_service.remove_message_handler(self._handle_message)
            self._cancel_timeout_timer()
            return
        client.send(request)

    def _handle_message(self, client: Client, msg: AccountListMessage) -> bool:
        """處理帳戶列表回應"""
        if not self._in_progress:
            return False

        if msg.payloadType == ProtoOAPayloadType.PROTO_OA_GET_ACCOUNTS_BY_ACCESS_TOKEN_RES:
            self._on_accounts_received(msg)
            return True

        if msg.payloadType == ProtoOAPayloadType.PROTO_OA_ERROR_RES:
            self._on_error(msg)
            return True

        return False

    def _on_accounts_received(self, msg: AccountListMessage) -> None:
        """帳戶列表接收成功"""
        self._end_operation()
        self._app_auth_service.remove_message_handler(self._handle_message)
        self._cancel_timeout_timer()
        accounts = self._parse_accounts(msg.ctidTraderAccount)
        self._log(f"✅ 已接收帳戶: {len(accounts)} 個")
        if self._callbacks.on_accounts_received:
            self._callbacks.on_accounts_received(accounts)

    def _on_error(self, msg: AccountListMessage) -> None:
        """帳戶列表接收失敗"""
        self._end_operation()
        self._app_auth_service.remove_message_handler(self._handle_message)
        self._cancel_timeout_timer()
        self._emit_error(f"錯誤 {msg.errorCode}: {msg.description}")

    def _start_timeout_timer(self, timeout_seconds: Optional[int]) -> None:
        if not timeout_seconds:
            return
        self._cancel_timeout_timer()
        self._timeout_timer = threading.Timer(timeout_seconds, self._on_timeout)
        self._timeout_timer.daemon = True
        self._timeout_timer.start()

    def _cancel_timeout_timer(self) -> None:
        if self._timeout_timer:
            self._timeout_timer.cancel()
            self._timeout_timer = None

    def _on_timeout(self) -> None:
        if not self._in_progress:
            return
        self._end_operation()
        self._app_auth_service.remove_message_handler(self._handle_message)
        self._emit_error("取得帳戶列表逾時")

    @staticmethod
    def _parse_accounts(raw_accounts: Sequence[AccountInfoMessage]) -> list:
        """解析原始帳戶資料"""
        return [
            {
                "account_id": int(account.ctidTraderAccountId),
                "is_live": bool(account.isLive),
                "trader_login": int(account.traderLogin) if account.traderLogin else None,
            }
            for account in raw_accounts
        ]
