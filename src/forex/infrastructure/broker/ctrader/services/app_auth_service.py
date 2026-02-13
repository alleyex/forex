"""
cTrader 應用程式層級認證服務
"""
from dataclasses import dataclass
import random
import threading
import time
from typing import Callable, Optional, Protocol

from ctrader_open_api import Client, Protobuf, TcpProtocol, EndPoints
from ctrader_open_api.messages.OpenApiCommonMessages_pb2 import ProtoHeartbeatEvent
from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAApplicationAuthReq
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOAPayloadType

from forex.infrastructure.broker.base import BaseCallbacks, build_callbacks
from forex.infrastructure.broker.ctrader.services.base import CTraderAuthServiceBase
from forex.infrastructure.broker.errors import ErrorCode, error_message
from forex.config.constants import MessageType, ConnectionStatus
from forex.config.paths import TOKEN_FILE
from forex.config.runtime import load_config
from forex.config.settings import AppCredentials
from forex.infrastructure.broker.ctrader.services.message_helpers import (
    format_confirm,
    format_error,
    format_success,
    format_unhandled,
    is_already_subscribed,
    is_non_subscribed_trendbar_unsubscribe,
)
from forex.utils.metrics import metrics
from forex.utils.reactor_manager import reactor_manager


@dataclass
class AppAuthServiceCallbacks(BaseCallbacks):
    """AppAuthService 的回調函式容器"""
    on_app_auth_success: Optional[Callable[[Client], None]] = None
    on_status_changed: Optional[Callable[[ConnectionStatus], None]] = None


class AppAuthMessage(Protocol):
    payloadType: int
    errorCode: int
    description: str


class AppAuthService(CTraderAuthServiceBase[AppAuthServiceCallbacks, AppAuthMessage]):
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
        connect_timeout: float = 20.0,
        reconnect_delay: float = 3.0,
        reconnect_max_delay: float = 60.0,
        reconnect_max_attempts: int = 0,
        reconnect_jitter_ratio: float = 0.15,
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
        self._connect_timeout = connect_timeout
        self._connect_started_ts: Optional[float] = None
        self._connect_watchdog_timer: Optional[threading.Timer] = None
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._last_message_ts: Optional[float] = None
        self._last_heartbeat_log_ts: Optional[float] = None
        self._heartbeat_log_interval = heartbeat_log_interval
        self._reconnect_delay = reconnect_delay
        self._reconnect_max_delay = max(reconnect_delay, reconnect_max_delay)
        self._reconnect_max_attempts = max(0, int(reconnect_max_attempts))
        self._reconnect_jitter_ratio = max(0.0, min(0.5, float(reconnect_jitter_ratio)))
        self._reconnect_attempt = 0
        self._reconnect_timer: Optional[threading.Timer] = None
        self._auto_reconnect = auto_reconnect
        self._manual_disconnect = False
        self._app_auth_retry_count = 0
        self._app_auth_retry_timer: Optional[threading.Timer] = None
        self._send_failure_streak = 0
        self._last_send_failure_ts: Optional[float] = None

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
            connect_timeout=max(10.0, runtime.heartbeat_timeout),
            reconnect_delay=runtime.reconnect_delay,
            reconnect_max_delay=runtime.reconnect_max_delay,
            reconnect_max_attempts=runtime.reconnect_max_attempts,
            reconnect_jitter_ratio=runtime.reconnect_jitter_ratio,
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
        self._manual_disconnect = False
        if self._status == ConnectionStatus.CONNECTING:
            self._log("ℹ️ 連線進行中，略過重複連線")
            return
        if self._status >= ConnectionStatus.APP_AUTHENTICATED and self._client is not None:
            self._log("ℹ️ 應用程式已認證，略過重複連線")
            return
        if not self._start_operation():
            self._log("⚠️ 已有連線流程進行中")
            return

        self._set_status(ConnectionStatus.CONNECTING)
        self._connect_started_ts = time.time()
        self._start_connect_watchdog()

        self._metrics_connect_started = time.monotonic()
        self._client = Client(self._host, self._port, TcpProtocol)
        self._send_wrapped = False
        self._wrap_client_send()
        self._client.setConnectedCallback(self._handle_connected)
        self._client.setDisconnectedCallback(self._handle_disconnected)
        self._client.setMessageReceivedCallback(self._handle_message)
        self._last_message_ts = time.time()

        self._log("🚀 正在連線到 cTrader...")
        reactor_manager.ensure_running()
        from twisted.internet import reactor
        reactor.callFromThread(self._client.startService)

    def disconnect(self) -> None:
        """手動中斷連線"""
        self._manual_disconnect = True
        self._stop_heartbeat_loop()
        self._end_operation()
        self.clear_message_handlers()
        self._cancel_reconnect_timer()
        self._cancel_connect_watchdog()
        if self._client is not None:
            self._stop_client_service(self._client, context="manual_disconnect")
        self._client = None
        self._send_wrapped = False
        self._set_status(ConnectionStatus.DISCONNECTED)
        self._reconnect_attempt = 0
        self._connect_started_ts = None
        self._log("🔌 已手動斷線")

    def get_credentials(self) -> AppCredentials:
        return self._credentials

    def seconds_since_last_message(self) -> Optional[float]:
        if self._last_message_ts is None:
            return None
        return max(0.0, time.time() - self._last_message_ts)

    def is_transport_fresh(self, *, max_idle_seconds: Optional[float] = None) -> bool:
        if self._status < ConnectionStatus.CONNECTED:
            return False
        age = self.seconds_since_last_message()
        if age is None:
            return False
        threshold = self._heartbeat_timeout if max_idle_seconds is None else max(1.0, float(max_idle_seconds))
        return age <= threshold

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
            # Ignore stale callbacks from old clients to avoid re-entering
            # duplicate auth flows during reconnect races.
            return
        # Any delayed reconnect timer from previous disconnects is obsolete now.
        self._cancel_reconnect_timer()
        # Reset watchdog window after TCP connects so AppAuth handshake gets
        # a full timeout budget instead of sharing the initial DNS/TCP delay.
        self._connect_started_ts = time.time()
        self._start_connect_watchdog()
        self._set_status(ConnectionStatus.CONNECTED)
        self._app_auth_retry_count = 0
        self._send_failure_streak = 0
        self._last_send_failure_ts = None
        self._cancel_app_auth_retry_timer()
        metrics.inc("ctrader.app_auth.connected")
        self._last_message_ts = time.time()
        self._start_heartbeat_loop()
        self._log(format_success("已連線！"))
        self._send_app_auth(client)

    def _handle_disconnected(self, client: Client, reason: str) -> None:
        """斷線後的回調"""
        if self._client is not client:
            return
        self._set_status(ConnectionStatus.DISCONNECTED)
        self._connect_started_ts = None
        self._stop_heartbeat_loop()
        self._end_operation()
        self.clear_message_handlers()
        self._cancel_connect_watchdog()
        self._cancel_app_auth_retry_timer()
        self._client = None
        self._send_wrapped = False
        self._send_failure_streak = 0
        self._last_send_failure_ts = None
        metrics.inc("ctrader.app_auth.disconnected")
        self._emit_error(error_message(ErrorCode.NETWORK, "已斷線", reason))
        if self._manual_disconnect:
            self._manual_disconnect = False
            self._cancel_reconnect_timer()
            return
        if self._auto_reconnect:
            if self._reconnect_timer is not None and self._reconnect_timer.is_alive():
                self._log("ℹ️ 重連已排程，等待下一次嘗試")
            else:
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
        self._send_failure_streak = 0

        # 內建處理器
        handled = self._handle_internal_message(client, msg, msg_type)

        # 外部註冊的處理器
        if self._dispatch_to_handlers(client, msg):
            handled = True

        if not handled:
            self._log(format_unhandled(msg_type))

    def _handle_internal_message(
        self, client: Client, msg: object, msg_type: int
    ) -> bool:
        """處理內建訊息類型"""
        handlers = {
            MessageType.APP_AUTH_RESPONSE: self._handle_app_auth_response,
            MessageType.ERROR_RESPONSE: self._handle_error_response,
            MessageType.HEARTBEAT: self._handle_heartbeat_event,
            ProtoOAPayloadType.PROTO_OA_SPOT_EVENT: self._handle_spot_event,
            ProtoOAPayloadType.PROTO_OA_SYMBOL_CHANGED_EVENT: self._handle_symbol_changed_event,
            ProtoOAPayloadType.PROTO_OA_ERROR_RES: self._handle_trading_error,
            ProtoOAPayloadType.PROTO_OA_UNSUBSCRIBE_SPOTS_RES: self._handle_unsubscribe_spots,
        }

        handler = handlers.get(msg_type)
        if handler:
            handler(client, msg)
            return True
        if self._is_noise_payload(msg_type):
            return True
        return False

    @staticmethod
    def _is_noise_payload(msg_type: int) -> bool:
        return msg_type in {
            2113,
            2125,
            2138,
            2166,
        }

    def _handle_heartbeat_event(self, client: Client, msg) -> None:
        """處理心跳事件（僅更新活躍時間）"""
        self._last_message_ts = time.time()

    def _handle_spot_event(self, client: Client, msg) -> None:
        """處理報價事件（避免未處理訊息噪音）"""
        return

    def _handle_symbol_changed_event(self, client: Client, msg) -> None:
        """處理商品變更事件（目前僅消化事件避免未處理訊息噪音）。"""
        return

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
        self._cancel_connect_watchdog()
        self._cancel_app_auth_retry_timer()
        self._connect_started_ts = None
        self._set_status(ConnectionStatus.APP_AUTHENTICATED)
        self._reconnect_attempt = 0
        self._log(format_success("應用程式已授權！"))
        metrics.inc("ctrader.app_auth.success")
        started_at = getattr(self, "_metrics_connect_started", None)
        if started_at is not None:
            metrics.observe("ctrader.app_auth.latency_s", time.monotonic() - started_at)

        if self._callbacks.on_app_auth_success:
            self._callbacks.on_app_auth_success(client)

    def _handle_error_response(self, client: Client, msg) -> None:
        """處理錯誤回應"""
        if is_already_subscribed(msg.errorCode, msg.description):
            return
        if is_non_subscribed_trendbar_unsubscribe(msg.errorCode, msg.description):
            return
        # After app auth is already established, generic ERROR_RESPONSE payloads
        # can belong to downstream account/trading flows. Do not tear down app
        # transport in that case; let higher-level handlers manage the error.
        if self._status >= ConnectionStatus.APP_AUTHENTICATED and not self._in_progress:
            metrics.inc("ctrader.app_auth.error.passive")
            self._emit_error(format_error(msg.errorCode, msg.description))
            return
        self._end_operation()
        self._set_status(ConnectionStatus.DISCONNECTED)
        metrics.inc("ctrader.app_auth.error")
        self._emit_error(format_error(msg.errorCode, msg.description))

    def _handle_trading_error(self, client: Client, msg) -> None:
        """處理交易相關錯誤回應（避免重複訂閱噪音）"""
        if is_already_subscribed(msg.errorCode, msg.description):
            return
        if is_non_subscribed_trendbar_unsubscribe(msg.errorCode, msg.description):
            return
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
        now = time.time()
        last_failure = self._last_send_failure_ts or 0.0
        if now - last_failure > 20.0:
            self._send_failure_streak = 0
        self._last_send_failure_ts = now
        self._send_failure_streak += 1
        if (
            self._status < ConnectionStatus.APP_AUTHENTICATED
            and self._client is not None
            and self._app_auth_retry_count < 2
            and self._auto_reconnect
        ):
            self._app_auth_retry_count += 1
            self._schedule_app_auth_retry()
        elif (
            self._status >= ConnectionStatus.APP_AUTHENTICATED
            and self._client is not None
            and self._auto_reconnect
            and self._send_failure_streak >= 6
        ):
            streak = self._send_failure_streak
            self._send_failure_streak = 0
            self._log(f"⚠️ 連續請求失敗 {streak} 次，主動重建連線")
            self._stop_client_service(self._client, context="send_failure_streak")
        return None

    def _schedule_app_auth_retry(self) -> None:
        self._cancel_app_auth_retry_timer()
        self._app_auth_retry_timer = threading.Timer(2.0, self._retry_app_auth_send)
        self._app_auth_retry_timer.daemon = True
        self._app_auth_retry_timer.start()

    def _cancel_app_auth_retry_timer(self) -> None:
        if self._app_auth_retry_timer and self._app_auth_retry_timer.is_alive():
            try:
                self._app_auth_retry_timer.cancel()
            except Exception:
                pass
        self._app_auth_retry_timer = None

    def _retry_app_auth_send(self) -> None:
        if self._status >= ConnectionStatus.APP_AUTHENTICATED:
            return
        if self._client is None:
            return
        self._log(f"🔁 重送應用程式認證請求 (retry {self._app_auth_retry_count})")
        try:
            reactor_manager.ensure_running()
            from twisted.internet import reactor
            reactor.callFromThread(self._send_app_auth, self._client)
        except Exception as exc:
            self._log(f"⚠️ 重送應用程式認證失敗: {exc}")

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

    def _stop_client_service(self, client: Optional[Client], *, context: str) -> None:
        if client is None:
            return
        try:
            reactor_manager.ensure_running()
            from twisted.internet import reactor
            reactor.callFromThread(client.stopService)
            return
        except Exception:
            pass
        try:
            client.stopService()
        except Exception as exc:  # pragma: no cover - best effort
            self._log(f"⚠️ 停止連線失敗 ({context}): {exc}")

    def _heartbeat_loop(self) -> None:
        while not self._heartbeat_stop.wait(self._heartbeat_interval):
            if not self._client or self._status < ConnectionStatus.CONNECTED:
                continue
            # During app-auth handshake, use connect watchdog instead of
            # heartbeat-idle timeout to avoid duplicate reconnect triggers.
            if self._status < ConnectionStatus.APP_AUTHENTICATED:
                self._send_heartbeat()
                continue
            if self._last_message_ts is not None:
                idle_seconds = time.time() - self._last_message_ts
                if idle_seconds > self._heartbeat_timeout:
                    self._log(f"⚠️ 超過 {self._heartbeat_timeout:.0f}s 未收到訊息，準備重連")
                    self._stop_client_service(self._client, context="heartbeat_timeout")
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
        next_attempt = self._reconnect_attempt + 1
        if self._reconnect_max_attempts > 0 and next_attempt > self._reconnect_max_attempts:
            self._log(
                f"⛔ {reason}：已達最大重連次數 ({self._reconnect_max_attempts})，停止自動重連"
            )
            return
        self._reconnect_attempt = next_attempt
        base_delay = min(
            self._reconnect_max_delay,
            self._reconnect_delay * (2 ** max(0, self._reconnect_attempt - 1)),
        )
        jitter = 1.0 + random.uniform(-self._reconnect_jitter_ratio, self._reconnect_jitter_ratio)
        delay = max(0.5, base_delay * jitter)
        self._log(
            f"🔄 {reason}，{delay:.1f}s 後重連 "
            f"(attempt {self._reconnect_attempt}"
            + (f"/{self._reconnect_max_attempts}" if self._reconnect_max_attempts > 0 else "")
            + ")"
        )
        self._reconnect_timer = threading.Timer(delay, self._reconnect)
        self._reconnect_timer.daemon = True
        self._reconnect_timer.start()

    def _cancel_reconnect_timer(self) -> None:
        if self._reconnect_timer and self._reconnect_timer.is_alive():
            try:
                self._reconnect_timer.cancel()
            except Exception:
                pass
        self._reconnect_timer = None

    def _start_connect_watchdog(self) -> None:
        self._cancel_connect_watchdog()
        self._connect_watchdog_timer = threading.Timer(self._connect_timeout, self._on_connect_timeout)
        self._connect_watchdog_timer.daemon = True
        self._connect_watchdog_timer.start()

    def _cancel_connect_watchdog(self) -> None:
        if self._connect_watchdog_timer and self._connect_watchdog_timer.is_alive():
            try:
                self._connect_watchdog_timer.cancel()
            except Exception:
                pass
        self._connect_watchdog_timer = None

    def _on_connect_timeout(self) -> None:
        if self._status >= ConnectionStatus.APP_AUTHENTICATED:
            return
        if self._status < ConnectionStatus.CONNECTED:
            timeout_reason = "連線逾時"
            timeout_log = f"⚠️ 連線逾時（>{self._connect_timeout:.0f}s），準備重連"
        else:
            timeout_reason = "App 認證逾時"
            timeout_log = f"⚠️ App 認證逾時（>{self._connect_timeout:.0f}s），準備重連"
        self._log(timeout_log)
        self._stop_client_service(self._client, context="connect_timeout")
        self._set_status(ConnectionStatus.DISCONNECTED)
        self._end_operation()
        self._client = None
        self._send_wrapped = False
        self._connect_started_ts = None
        if self._auto_reconnect:
            self._schedule_reconnect(timeout_reason)

    def _reconnect(self) -> None:
        reactor_manager.ensure_running()
        from twisted.internet import reactor
        reactor.callFromThread(self._reconnect_on_reactor)

    def _reconnect_on_reactor(self) -> None:
        if self._status in (
            ConnectionStatus.CONNECTED,
            ConnectionStatus.APP_AUTHENTICATED,
            ConnectionStatus.ACCOUNT_AUTHENTICATED,
        ) and self._client is not None:
            # Already recovered by another reconnect path; ignore stale timer fire.
            return
        if self._status == ConnectionStatus.CONNECTING:
            started = self._connect_started_ts or 0.0
            if started and (time.time() - started) < self._connect_timeout:
                return
            try:
                if self._client is not None:
                    self._client.stopService()
            except Exception:
                pass
            self._client = None
            self._send_wrapped = False
            self._end_operation()
            self._set_status(ConnectionStatus.DISCONNECTED)
            self._connect_started_ts = None
        if self._client is not None:
            try:
                self._client.stopService()
            except Exception:
                pass
        self.connect()
