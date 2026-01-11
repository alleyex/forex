from typing import Callable, Optional, Protocol
from dataclasses import dataclass, field

from ctrader_open_api import Client, Protobuf, TcpProtocol, EndPoints
from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAApplicationAuthReq

from config.constants import MessageType, ConnectionStatus
from config.settings import AppCredentials


class AuthCallbacks(Protocol):
    """Protocol defining expected callbacks"""
    def on_app_auth_success(self, client: Client) -> None: ...
    def on_error(self, error: str) -> None: ...
    def on_log(self, message: str) -> None: ...
    def on_status_changed(self, status: ConnectionStatus) -> None: ...


@dataclass
class AppAuthServiceCallbacks:
    """Callback container with defaults"""
    on_app_auth_success: Optional[Callable[[Client], None]] = None
    on_error: Optional[Callable[[str], None]] = None
    on_log: Optional[Callable[[str], None]] = None
    on_status_changed: Optional[Callable[[ConnectionStatus], None]] = None


class AppAuthService:
    """
    Handles application-level authentication with cTrader Open API.
    
    Usage:
        service = AppAuthService.create("demo", "token.json")
        service.set_callbacks(callbacks)
        service.connect()
    """
    
    def __init__(
        self, 
        credentials: AppCredentials,
        host: str,
        port: int,
    ):
        self._credentials = credentials
        self._host = host
        self._port = port
        self._status = ConnectionStatus.DISCONNECTED
        self._callbacks = AppAuthServiceCallbacks()
        self._client: Optional[Client] = None

    @classmethod
    def create(cls, host_type: str, token_file: str) -> "AppAuthService":
        """Factory method to create service with configuration"""
        credentials = AppCredentials.from_file(token_file)
        
        host = (
            EndPoints.PROTOBUF_DEMO_HOST 
            if host_type == "demo" 
            else EndPoints.PROTOBUF_LIVE_HOST
        )
        
        return cls(
            credentials=credentials,
            host=host,
            port=EndPoints.PROTOBUF_PORT,
        )

    @property
    def status(self) -> ConnectionStatus:
        return self._status
    
    @property
    def is_app_authenticated(self) -> bool:
        return self._status >= ConnectionStatus.APP_AUTHENTICATED

    def set_callbacks(
        self,
        on_app_auth_success: Optional[Callable[[Client], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
        on_status_changed: Optional[Callable[[ConnectionStatus], None]] = None,
    ) -> None:
        """Set callback functions for various events"""
        self._callbacks = AppAuthServiceCallbacks(
            on_app_auth_success=on_app_auth_success,
            on_error=on_error,
            on_log=on_log,
            on_status_changed=on_status_changed,
        )

    def connect(self) -> None:
        """Initialize connection and start authentication flow"""
        self._set_status(ConnectionStatus.CONNECTING)
        
        self._client = Client(self._host, self._port, TcpProtocol)
        self._client.setConnectedCallback(self._handle_connected)
        self._client.setDisconnectedCallback(self._handle_disconnected)
        self._client.setMessageReceivedCallback(self._handle_message)
        
        self._log("🚀 Connecting to cTrader...")
        self._client.startService()

    def get_client(self) -> Client:
        """Get the authenticated client for use by other services"""
        if not self.is_app_authenticated:
            raise RuntimeError("Application not authenticated yet")
        if self._client is None:
            raise RuntimeError("Client not initialized")
        return self._client

    # ─────────────────────────────────────────────────────────────
    # Private Methods
    # ─────────────────────────────────────────────────────────────

    def _set_status(self, status: ConnectionStatus) -> None:
        """Update status and notify callback"""
        self._status = status
        if self._callbacks.on_status_changed:
            self._callbacks.on_status_changed(status)

    def _log(self, message: str) -> None:
        """Log message through callback or print"""
        if self._callbacks.on_log:
            self._callbacks.on_log(message)
        else:
            print(message)

    def _emit_error(self, error: str) -> None:
        """Emit error through callback"""
        self._log(f"❌ {error}")
        if self._callbacks.on_error:
            self._callbacks.on_error(error)

    def _handle_connected(self, client: Client) -> None:
        """Callback when TCP connection established"""
        self._set_status(ConnectionStatus.CONNECTED)
        self._log("✅ Connected!")
        self._send_app_auth(client)

    def _handle_disconnected(self, client: Client, reason: str) -> None:
        """Callback when disconnected"""
        self._set_status(ConnectionStatus.DISCONNECTED)
        self._emit_error(f"Disconnected: {reason}")

    def _send_app_auth(self, client: Client) -> None:
        """Send application authentication request"""
        request = ProtoOAApplicationAuthReq()
        request.clientId = self._credentials.client_id
        request.clientSecret = self._credentials.client_secret
        
        self._log("📤 Sending Application Auth...")
        client.send(request)

    def _handle_message(self, client: Client, message) -> None:
        """Route incoming messages to appropriate handlers"""
        msg = Protobuf.extract(message)
        msg_type = msg.payloadType
        
        handlers = {
            MessageType.APP_AUTH_RESPONSE: self._handle_app_auth_response,
            MessageType.ERROR_RESPONSE: self._handle_error_response,
            MessageType.HEARTBEAT: self._handle_heartbeat,
        }
        
        handler = handlers.get(msg_type)
        if handler:
            handler(client, msg)
        else:
            self._log(f"📩 Unhandled message type: {msg_type}")

    def _handle_app_auth_response(self, client: Client, msg) -> None:
        """Handle successful application authentication"""
        self._set_status(ConnectionStatus.APP_AUTHENTICATED)
        self._log("✅ Application Authorized!")
        
        if self._callbacks.on_app_auth_success:
            self._callbacks.on_app_auth_success(client)

    def _handle_error_response(self, client: Client, msg) -> None:
        """Handle error response from server"""
        error_msg = f"Error {msg.errorCode}: {msg.description}"
        self._emit_error(error_msg)

    def _handle_heartbeat(self, client: Client, msg) -> None:
        """Handle heartbeat (no action needed)"""
        pass