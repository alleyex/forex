"""Account list service."""
from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from ctrader_open_api import Client
from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAGetAccountListByAccessTokenReq
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOAPayloadType

from forex.infrastructure.broker.base import (
    BaseCallbacks,
    LogHistoryMixin,
    OperationStateMixin,
    build_callbacks,
)
from forex.infrastructure.broker.ctrader.services.app_auth_service import AppAuthService
from forex.infrastructure.broker.ctrader.services.base import CTraderRequestLifecycleMixin
from forex.infrastructure.broker.ctrader.services.message_helpers import (
    dispatch_payload,
    format_error,
    format_request,
    format_success,
    format_warning,
)
from forex.infrastructure.broker.ctrader.services.timeout_tracker import TimeoutTracker
from forex.infrastructure.broker.errors import ErrorCode, error_message
from forex.utils.metrics import metrics


class AccountInfoMessage(Protocol):
    ctidTraderAccountId: int
    isLive: bool
    traderLogin: int | None
    lastClosingDealTimestamp: int | None
    lastBalanceUpdateTimestamp: int | None


class AccountListMessage(Protocol):
    payloadType: int
    errorCode: int
    description: str
    permissionScope: int | None
    ctidTraderAccount: Sequence[AccountInfoMessage]


@dataclass
class AccountListServiceCallbacks(BaseCallbacks):
    """Callbacks for AccountListService."""
    on_accounts_received: Callable[[list], None] | None = None


class AccountListService(
    CTraderRequestLifecycleMixin,
    LogHistoryMixin[AccountListServiceCallbacks],
    OperationStateMixin,
):
    """
    Fetch the account list using an access token.

    Usage:
        service = AccountListService(app_auth_service, access_token)
        service.set_callbacks(on_accounts_received=..., on_error=...)
        service.fetch()
    """

    def __init__(self, app_auth_service: AppAuthService, access_token: str):
        self._app_auth_service = app_auth_service
        self._access_token = access_token
        self._callbacks = AccountListServiceCallbacks()
        self._in_progress = False
        self._timeout_tracker = TimeoutTracker(self._on_timeout)
        self._log_history = []

    def set_access_token(self, access_token: str) -> None:
        self._access_token = access_token

    def set_callbacks(
        self,
        on_accounts_received: Callable[[list], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        on_log: Callable[[str], None] | None = None,
    ) -> None:
        """Set callbacks."""
        self._callbacks = build_callbacks(
            AccountListServiceCallbacks,
            on_accounts_received=on_accounts_received,
            on_error=on_error,
            on_log=on_log,
        )
        self._replay_log_history()

    def fetch(self, timeout_seconds: int | None = None) -> None:
        """Fetch the account list."""
        if not self._access_token:
            self._emit_error(error_message(ErrorCode.VALIDATION, "Missing access token"))
            return

        if not self._start_operation():
            return

        self._begin_request_lifecycle(
            timeout_tracker=self._timeout_tracker,
            timeout_seconds=timeout_seconds,
            retry_request=self._retry_request,
            handler=self._handle_message,
            send_request=self._send_request,
        )

    def _send_request(self) -> None:
        """Send the account list request."""
        request = ProtoOAGetAccountListByAccessTokenReq()
        request.accessToken = self._access_token
        self._log(format_request("Fetching account list..."))
        if not self._send_request_with_client(
            request=request,
            timeout_tracker=self._timeout_tracker,
            handler=self._handle_message,
        ):
            return

    def _handle_message(self, client: Client, msg: AccountListMessage) -> bool:
        """Handle the account list response."""
        if not self._in_progress:
            return False
        return dispatch_payload(
            msg,
            {
                ProtoOAPayloadType.PROTO_OA_GET_ACCOUNTS_BY_ACCESS_TOKEN_RES: (
                    self._on_accounts_received
                ),
                ProtoOAPayloadType.PROTO_OA_ERROR_RES: self._on_error,
            },
        )

    def _on_accounts_received(self, msg: AccountListMessage) -> None:
        """Handle successful account list retrieval."""
        self._cleanup_request_lifecycle(
            timeout_tracker=self._timeout_tracker,
            handler=self._handle_message,
        )
        permission_scope = getattr(msg, "permissionScope", None)
        accounts = self._parse_accounts(msg.ctidTraderAccount, permission_scope)
        self._log(format_success(f"Received accounts: {len(accounts)}"))
        metrics.inc("ctrader.account_list.success")
        started_at = getattr(self, "_metrics_started_at", None)
        if started_at is not None:
            metrics.observe(
                "ctrader.account_list.latency_s",
                time.monotonic() - started_at,
            )
        if self._callbacks.on_accounts_received:
            self._callbacks.on_accounts_received(accounts)

    def _on_error(self, msg: AccountListMessage) -> None:
        """Handle account list retrieval failure."""
        self._cleanup_request_lifecycle(
            timeout_tracker=self._timeout_tracker,
            handler=self._handle_message,
        )
        metrics.inc("ctrader.account_list.error")
        self._emit_error(format_error(msg.errorCode, msg.description))

    def _on_timeout(self) -> None:
        if not self._in_progress:
            return
        self._cleanup_request_lifecycle(
            timeout_tracker=self._timeout_tracker,
            handler=self._handle_message,
        )
        metrics.inc("ctrader.account_list.timeout")
        self._emit_error(error_message(ErrorCode.TIMEOUT, "Account list request timed out"))

    def _retry_request(self, attempt: int) -> None:
        if not self._in_progress:
            return
        self._log(format_warning(f"Account list timed out, retry attempt {attempt}"))
        metrics.inc("ctrader.account_list.retry")
        self._send_request()

    @staticmethod
    def _parse_accounts(
        raw_accounts: Sequence[AccountInfoMessage],
        permission_scope: int | None,
    ) -> list:
        """Parse raw account data."""
        return [
            {
                "account_id": int(account.ctidTraderAccountId),
                "is_live": bool(account.isLive),
                "trader_login": int(account.traderLogin) if account.traderLogin else None,
                "permission_scope": permission_scope,
                "last_closing_deal_timestamp": (
                    int(getattr(account, "lastClosingDealTimestamp", 0)) or None
                ),
                "last_balance_update_timestamp": (
                    int(getattr(account, "lastBalanceUpdateTimestamp", 0)) or None
                ),
            }
            for account in raw_accounts
        ]
