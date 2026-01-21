"""
cTrader 應用程式層級認證服務
"""
from dataclasses import dataclass
import threading
import time
from typing import Callable, Optional, Protocol

from ctrader_open_api import Client, Protobuf, TcpProtocol, EndPoints
from ctrader_open_api.messages.OpenApiCommonMessages_pb2 import ProtoHeartbeatEvent
from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAApplicationAuthReq
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOAPayloadType

from broker.base import BaseAuthService, BaseCallbacks, build_callbacks
from config.constants import MessageType, ConnectionStatus
from config.paths import TOKEN_FILE
from config.runtime import load_config
from config.settings import AppCredentials
from infrastructure.broker.ctrader.services.message_helpers import (
    format_confirm,
    format_error,
    format_success,
    is_already_subscribed,
)


@dataclass
class AppAuthServiceCallbacks(BaseCallbacks):
    """AppAuthService 的回調函式容器"""
    on_app_auth_success: Optional[Callable[[Client], None]] = None
    on_status_changed: Optional[Callable[[ConnectionStatus], None]] = None


class AppAuthMessage(Protocol):
    payloadType: int
    errorCode: int
    description: str


class AppAuthService(BaseAuthService[AppAuthServiceCallbacks, Client, AppAuthMessage]):
    """
    處理 cTrader Open API 的應用程式層級認證

    使用方式：
        service = AppAuthService.create("demo", TOKEN_FILE)
        service.set_callbacks(
            on_app_auth_success=lambda client: print("成功"),
            on_error=lambda err: print(f"錯誤: {err}"),
        )
        service.connect()

    Attributes:
        status: 目前的連線狀態
        is_app_authenticated: 是否已完成應用程式認證
    """

    def __init__(
        self,
        credentials: AppCredentials,
        host: str,
        port: int,
        heartbeat_interval: float = 10.0,
        heartbeat_timeout: float = 30.0,
        reconnect_delay: float = 3.0,
        auto_reconnect: bool = True,
        heartbeat_log_interval: float = 60.0,
    ):
        super().__init__(callbacks=AppAuthServiceCallbacks())
        self._credentials = credentials
        self._host = host
        self._port = port
        self._client: Optional[Client] = None
        self._send_wrapped = False
        self._raw_client_send = None
        self._heartbeat_interval = heartbeat_interval
        self._heartbeat_timeout = heartbeat_timeout
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._last_message_ts: Optional[float] = None
        self._last_heartbeat_log_ts: Optional[float] = None
        self._heartbeat_log_interval = heartbeat_log_interval
        self._reconnect_delay = reconnect_delay
        self._reconnect_timer: Optional[threading.Timer] = None
        self._auto_reconnect = auto_reconnect

    @classmethod
    def create(cls, host_type: str, token_file: str = TOKEN_FILE) -> "AppAuthService":
        """
        工廠方法：從設定檔建立服務實例

        Args:
            host_type: "demo" 或 "live"
            token_file: 憑證檔案路徑

        Returns:
            AppAuthService 實例

        Raises:
            FileNotFoundError: 找不到憑證檔案
            ValueError: 憑證格式錯誤
        """
        credentials = AppCredentials.from_file(token_file)
        runtime = load_config()
        host = cls._resolve_host(host_type)
        return cls(
            credentials=credentials,
            host=host,
            port=EndPoints.PROTOBUF_PORT,
            heartbeat_interval=runtime.heartbeat_interval,
            heartbeat_timeout=runtime.heartbeat_timeout,
            reconnect_delay=runtime.reconnect_delay,
            auto_reconnect=runtime.auto_reconnect,
            heartbeat_log_interval=runtime.heartbeat_log_interval,
        )

    @staticmethod
    def _resolve_host(host_type: str) -> str:
        """解析主機類型為實際主機位址"""
        hosts = {
            "demo": EndPoints.PROTOBUF_DEMO_HOST,
            "live": EndPoints.PROTOBUF_LIVE_HOST,
        }
        return hosts.get(host_type, EndPoints.PROTOBUF_DEMO_HOST)

    @property
    def is_app_authenticated(self) -> bool:
        """檢查是否已完成應用程式認證"""
        return self._status >= ConnectionStatus.APP_AUTHENTICATED

    def set_callbacks(
        self,
        on_app_auth_success: Optional[Callable[[Client], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
        on_status_changed: Optional[Callable[[ConnectionStatus], None]] = None,
    ) -> None:
        """設定回調函式"""
        self._callbacks = build_callbacks(
            AppAuthServiceCallbacks,
            on_app_auth_success=on_app_auth_success,
            on_error=on_error,
            on_log=on_log,
            on_status_changed=on_status_changed,
        )
        self._replay_log_history()

    def connect(self) -> None:
        """初始化連線並開始認證流程"""
        if self._status >= ConnectionStatus.APP_AUTHENTICATED and self._client is not None:
            self._log("ℹ️ 應用程式已認證，略過重複連線")
            return
        if not self._start_operation():
            self._log("⚠️ 已有連線流程進行中")
            return

        self._set_status(ConnectionStatus.CONNECTING)

        self._client = Client(self._host, self._port, TcpProtocol)
        self._send_wrapped = False
        self._wrap_client_send()
        self._client.setConnectedCallback(self._handle_connected)
        self._client.setDisconnectedCallback(self._handle_disconnected)
        self._client.setMessageReceivedCallback(self._handle_message)
        self._last_message_ts = time.time()

        self._log("🚀 正在連線到 cTrader...")
        self._client.startService()

    def get_client(self) -> Client:
        """
        取得已認證的 Client 實例

        Returns:
            Client 實例

        Raises:
            RuntimeError: 尚未完成認證或 Client 未初始化
        """
        if not self.is_app_authenticated:
            raise RuntimeError("應用程式尚未完成認證")
        if self._client is None:
            raise RuntimeError("Client 尚未初始化")
        return self._client

    # ─────────────────────────────────────────────────────────────
    # 連線回調處理
    # ─────────────────────────────────────────────────────────────

    def _handle_connected(self, client: Client) -> None:
        """TCP 連線建立後的回調"""
        if self._client is not client:
            self._client = client
        self._set_status(ConnectionStatus.CONNECTED)
        self._last_message_ts = time.time()
        self._start_heartbeat_loop()
        self._log(format_success("已連線！"))
        self._send_app_auth(client)

    def _handle_disconnected(self, client: Client, reason: str) -> None:
        """斷線後的回調"""
        if self._client is not client:
            return
        self._set_status(ConnectionStatus.DISCONNECTED)
        self._stop_heartbeat_loop()
        self._end_operation()
        self.clear_message_handlers()
        self._client = None
        self._send_wrapped = False
        self._emit_error(f"已斷線: {reason}")
        if self._auto_reconnect:
            self._log("🔄 偵測到斷線，將自動嘗試重新連線")
            self._schedule_reconnect("連線中斷")

    def _send_app_auth(self, client: Client) -> None:
        """發送應用程式認證請求"""
        request = ProtoOAApplicationAuthReq()
        request.clientId = self._credentials.client_id
        request.clientSecret = self._credentials.client_secret

        self._log("📤 正在發送應用程式認證...")
        client.send(request)

    # ─────────────────────────────────────────────────────────────
    # 訊息處理
    # ─────────────────────────────────────────────────────────────

    def _handle_message(self, client: Client, message) -> None:
        """路由傳入的訊息到適當的處理器"""
        if self._client is not client:
            return
        msg = Protobuf.extract(message)
        msg_type = msg.payloadType
        self._last_message_ts = time.time()

        # 內建處理器
        handled = self._handle_internal_message(client, msg, msg_type)

        # 外部註冊的處理器
        if self._dispatch_to_handlers(client, msg):
            handled = True

        if not handled:
            self._log(f"📩 未處理的訊息類型: {msg_type}")

    def _handle_internal_message(
        self, client: Client, msg: object, msg_type: int
    ) -> bool:
        """處理內建訊息類型"""
        handlers = {
            MessageType.APP_AUTH_RESPONSE: self._handle_app_auth_response,
            MessageType.ERROR_RESPONSE: self._handle_error_response,
            MessageType.HEARTBEAT: self._handle_heartbeat_event,
            ProtoOAPayloadType.PROTO_OA_SPOT_EVENT: self._handle_spot_event,
            ProtoOAPayloadType.PROTO_OA_UNSUBSCRIBE_SPOTS_RES: self._handle_unsubscribe_spots,
        }

        handler = handlers.get(msg_type)
        if handler:
            handler(client, msg)
            return True
        return False

    def _handle_heartbeat_event(self, client: Client, msg) -> None:
        """處理心跳事件（僅更新活躍時間）"""
        self._last_message_ts = time.time()

    def _handle_spot_event(self, client: Client, msg) -> None:
        """處理報價事件（避免未處理訊息噪音）"""
        self._log(format_confirm("收到報價事件", ProtoOAPayloadType.PROTO_OA_SPOT_EVENT))

    def _handle_unsubscribe_spots(self, client: Client, msg) -> None:
        """處理報價退訂回應"""
        self._log(
            format_confirm(
                "報價退訂已確認",
                ProtoOAPayloadType.PROTO_OA_UNSUBSCRIBE_SPOTS_RES,
            )
        )

    def _handle_app_auth_response(self, client: Client, msg) -> None:
        """處理應用程式認證成功回應"""
        if self._client is None:
            self._client = client
        self._end_operation()
        self._set_status(ConnectionStatus.APP_AUTHENTICATED)
        self._log(format_success("應用程式已授權！"))

        if self._callbacks.on_app_auth_success:
            self._callbacks.on_app_auth_success(client)

    def _handle_error_response(self, client: Client, msg) -> None:
        """處理錯誤回應"""
        if is_already_subscribed(msg.errorCode, msg.description):
            return
        self._end_operation()
        self._set_status(ConnectionStatus.DISCONNECTED)
        self._emit_error(format_error(msg.errorCode, msg.description))

    def _wrap_client_send(self) -> None:
        if not self._client or self._send_wrapped:
            return
        original_send = self._client.send
        self._raw_client_send = original_send

        def _send_with_errback(message, *args, **kwargs):
            deferred = original_send(message, *args, **kwargs)
            if hasattr(deferred, "addErrback"):
                deferred.addErrback(self._handle_send_failure)
            return deferred

        self._client.send = _send_with_errback  # type: ignore[assignment]
        self._send_wrapped = True

    def _handle_send_failure(self, failure) -> None:
        message = getattr(failure, "getErrorMessage", lambda: str(failure))()
        self._log(f"⚠️ 請求逾時或失敗: {message}")
        return None

    def _start_heartbeat_loop(self) -> None:
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            return
        self._heartbeat_stop.clear()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            name="ctrader-heartbeat",
            daemon=True,
        )
        self._heartbeat_thread.start()

    def _stop_heartbeat_loop(self) -> None:
        self._heartbeat_stop.set()
        self._heartbeat_thread = None

    def _heartbeat_loop(self) -> None:
        while not self._heartbeat_stop.wait(self._heartbeat_interval):
            if not self._client or self._status < ConnectionStatus.CONNECTED:
                continue
            if self._last_message_ts is not None:
                idle_seconds = time.time() - self._last_message_ts
                if idle_seconds > self._heartbeat_timeout:
                    self._log(f"⚠️ 超過 {self._heartbeat_timeout:.0f}s 未收到訊息，準備重連")
                    try:
                        self._client.stopService()
                    except Exception as exc:
                        self._log(f"⚠️ 停止連線失敗: {exc}")
                    continue
            self._send_heartbeat()

    def _send_heartbeat(self) -> None:
        if not self._client:
            return
        now = time.time()
        if (
            self._last_heartbeat_log_ts is None
            or now - self._last_heartbeat_log_ts >= self._heartbeat_log_interval
        ):
            self._log("💓 發送 heartbeat")
            self._last_heartbeat_log_ts = now
        send_fn = self._raw_client_send or self._client.send
        try:
            deferred = send_fn(ProtoHeartbeatEvent(), responseTimeoutInSeconds=2)
            if hasattr(deferred, "addErrback"):
                deferred.addErrback(lambda failure: None)
        except Exception as exc:
            self._log(f"⚠️ 心跳發送失敗: {exc}")

    def _schedule_reconnect(self, reason: str) -> None:
        if self._reconnect_timer and self._reconnect_timer.is_alive():
            return
        self._log(f"🔄 {reason}，{self._reconnect_delay:.0f}s 後重連")
        self._reconnect_timer = threading.Timer(self._reconnect_delay, self._reconnect)
        self._reconnect_timer.daemon = True
        self._reconnect_timer.start()

    def _reconnect(self) -> None:
        if self._status == ConnectionStatus.CONNECTING:
            return
        if self._client is not None:
            try:
                self._client.stopService()
            except Exception:
                pass
        self.connect()
