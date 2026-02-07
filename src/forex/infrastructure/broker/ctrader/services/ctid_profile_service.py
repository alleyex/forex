"""
CTID Profile 服務
"""
from dataclasses import dataclass
import time
from typing import Callable, Optional, Protocol

from ctrader_open_api import Client
from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAGetCtidProfileByTokenReq
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOAPayloadType

from forex.infrastructure.broker.base import BaseCallbacks, LogHistoryMixin, OperationStateMixin, build_callbacks
from forex.infrastructure.broker.errors import ErrorCode, error_message
from forex.config.runtime import load_config, retry_policy_from_config
from forex.infrastructure.broker.ctrader.services.app_auth_service import AppAuthService
from forex.infrastructure.broker.ctrader.services.message_helpers import (
    dispatch_payload,
    format_error,
    format_request,
    format_success,
    format_warning,
)
from forex.infrastructure.broker.ctrader.services.timeout_tracker import TimeoutTracker
from forex.utils.metrics import metrics


class ProfileMessage(Protocol):
    userId: int


class ProfileResponseMessage(Protocol):
    payloadType: int
    errorCode: int
    description: str
    profile: Optional[ProfileMessage]


@dataclass
class CtidProfile:
    user_id: Optional[int]


@dataclass
class CtidProfileServiceCallbacks(BaseCallbacks):
    on_profile_received: Optional[Callable[[CtidProfile], None]] = None


class CtidProfileService(LogHistoryMixin[CtidProfileServiceCallbacks], OperationStateMixin):
    """
    透過存取權杖取得 CTID Profile
    """

    def __init__(self, app_auth_service: AppAuthService, access_token: str):
        self._app_auth_service = app_auth_service
        self._access_token = access_token
        self._callbacks = CtidProfileServiceCallbacks()
        self._in_progress = False
        self._timeout_tracker = TimeoutTracker(self._on_timeout)
        self._log_history = []

    def set_access_token(self, access_token: str) -> None:
        self._access_token = access_token

    def set_callbacks(
        self,
        on_profile_received: Optional[Callable[[CtidProfile], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._callbacks = build_callbacks(
            CtidProfileServiceCallbacks,
            on_profile_received=on_profile_received,
            on_error=on_error,
            on_log=on_log,
        )
        self._replay_log_history()

    def fetch(self, timeout_seconds: Optional[int] = None) -> None:
        if not self._access_token:
            self._emit_error(error_message(ErrorCode.VALIDATION, "缺少存取權杖"))
            return

        if not self._start_operation():
            return

        runtime = load_config()
        self._metrics_started_at = time.monotonic()
        self._timeout_tracker.configure_retry(
            retry_policy_from_config(runtime),
            self._retry_request,
        )
        self._app_auth_service.add_message_handler(self._handle_message)
        self._timeout_tracker.start(timeout_seconds or runtime.request_timeout)
        self._send_request()

    def _send_request(self) -> None:
        request = ProtoOAGetCtidProfileByTokenReq()
        request.accessToken = self._access_token
        self._log(format_request("正在取得 CTID Profile..."))
        try:
            client = self._app_auth_service.get_client()
        except Exception as exc:
            self._emit_error(str(exc))
            self._end_operation()
            self._app_auth_service.remove_message_handler(self._handle_message)
            self._timeout_tracker.cancel()
            return
        client.send(request)

    def _handle_message(self, client: Client, msg: ProfileResponseMessage) -> bool:
        if not self._in_progress:
            return False
        return dispatch_payload(
            msg,
            {
                ProtoOAPayloadType.PROTO_OA_GET_CTID_PROFILE_BY_TOKEN_RES: self._on_profile_received,
                ProtoOAPayloadType.PROTO_OA_ERROR_RES: self._on_error,
            },
        )

    def _on_profile_received(self, msg: ProfileResponseMessage) -> None:
        self._end_operation()
        self._app_auth_service.remove_message_handler(self._handle_message)
        self._timeout_tracker.cancel()
        profile = getattr(msg, "profile", None)
        user_id = None if profile is None else int(getattr(profile, "userId", 0))
        data = CtidProfile(user_id=user_id if user_id else None)
        self._log(format_success("已接收 CTID Profile"))
        metrics.inc("ctrader.ctid_profile.success")
        started_at = getattr(self, "_metrics_started_at", None)
        if started_at is not None:
            metrics.observe("ctrader.ctid_profile.latency_s", time.monotonic() - started_at)
        if self._callbacks.on_profile_received:
            self._callbacks.on_profile_received(data)

    def _on_error(self, msg: ProfileResponseMessage) -> None:
        self._end_operation()
        self._app_auth_service.remove_message_handler(self._handle_message)
        self._timeout_tracker.cancel()
        metrics.inc("ctrader.ctid_profile.error")
        self._emit_error(format_error(msg.errorCode, msg.description))

    def _on_timeout(self) -> None:
        if not self._in_progress:
            return
        self._end_operation()
        self._app_auth_service.remove_message_handler(self._handle_message)
        metrics.inc("ctrader.ctid_profile.timeout")
        self._emit_error(error_message(ErrorCode.TIMEOUT, "取得 CTID Profile 逾時"))

    def _retry_request(self, attempt: int) -> None:
        if not self._in_progress:
            return
        self._log(format_warning(f"CTID Profile 逾時，重試第 {attempt} 次"))
        metrics.inc("ctrader.ctid_profile.retry")
        self._send_request()
