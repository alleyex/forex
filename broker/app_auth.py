"""
cTrader 應用程式層級認證服務
"""
from typing import Callable, Optional, Protocol
from dataclasses import dataclass

from ctrader_open_api import Client, Protobuf, TcpProtocol, EndPoints
from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAApplicationAuthReq

from broker.base import BaseAuthService, BaseCallbacks, build_callbacks
from config.constants import MessageType, ConnectionStatus
from config.settings import AppCredentials


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
        service = AppAuthService.create("demo", "token.json")
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
    ):
        super().__init__(callbacks=AppAuthServiceCallbacks())
        self._credentials = credentials
        self._host = host
        self._port = port
        self._client: Optional[Client] = None

    @classmethod
    def create(cls, host_type: str, token_file: str) -> "AppAuthService":
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
        host = cls._resolve_host(host_type)
        return cls(
            credentials=credentials,
            host=host,
            port=EndPoints.PROTOBUF_PORT,
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

    def connect(self) -> None:
        """初始化連線並開始認證流程"""
        if not self._start_operation():
            self._log("⚠️ 已有連線流程進行中")
            return

        self._set_status(ConnectionStatus.CONNECTING)
        
        self._client = Client(self._host, self._port, TcpProtocol)
        self._client.setConnectedCallback(self._handle_connected)
        self._client.setDisconnectedCallback(self._handle_disconnected)
        self._client.setMessageReceivedCallback(self._handle_message)
        
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
        self._set_status(ConnectionStatus.CONNECTED)
        self._log("✅ 已連線！")
        self._send_app_auth(client)

    def _handle_disconnected(self, client: Client, reason: str) -> None:
        """斷線後的回調"""
        self._set_status(ConnectionStatus.DISCONNECTED)
        self._end_operation()
        self.clear_message_handlers()
        self._emit_error(f"已斷線: {reason}")

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
        msg = Protobuf.extract(message)
        msg_type = msg.payloadType
        
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
            MessageType.HEARTBEAT: self._handle_heartbeat,
        }
        
        handler = handlers.get(msg_type)
        if handler:
            handler(client, msg)
            return True
        return False

    def _handle_app_auth_response(self, client: Client, msg) -> None:
        """處理應用程式認證成功回應"""
        self._end_operation()
        self._set_status(ConnectionStatus.APP_AUTHENTICATED)
        self._log("✅ 應用程式已授權！")
        
        if self._callbacks.on_app_auth_success:
            self._callbacks.on_app_auth_success(client)

    def _handle_error_response(self, client: Client, msg) -> None:
        """處理錯誤回應"""
        error_msg = f"錯誤 {msg.errorCode}: {msg.description}"
        self._end_operation()
        self._set_status(ConnectionStatus.DISCONNECTED)
        self._emit_error(error_msg)

    def _handle_heartbeat(self, client: Client, msg) -> None:
        """處理心跳（無需動作）"""
        pass
