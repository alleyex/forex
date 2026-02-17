"""
cTrader app auth dialog
"""
from typing import Optional

from PySide6.QtWidgets import (
    QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QFormLayout, QWidget, QHBoxLayout,
    QRadioButton, QButtonGroup,
)
from PySide6.QtCore import Signal, Slot

from forex.ui.shared.dialogs.base_auth_dialog import BaseAuthDialog
from forex.ui.shared.widgets.layout_helpers import configure_form_layout
from forex.application.broker.protocols import AppAuthServiceLike
from forex.application.broker.use_cases import BrokerUseCases
from forex.application.events import EventBus
from forex.application.state import AppState
from forex.config.constants import ConnectionStatus
from forex.config.paths import TOKEN_FILE
from forex.config.settings import AppCredentials
from forex.utils.reactor_manager import reactor_manager
from forex.ui.shared.utils.formatters import format_connection_message


class CredentialsFormWidget(QWidget):
    """憑證輸入表單元件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        layout = QFormLayout(self)
        configure_form_layout(layout, horizontal_spacing=12, vertical_spacing=10)

        # Environment選擇
        self._host_type = "demo"
        self._host_locked = False
        self._host_group = QButtonGroup(self)
        self._host_demo = QRadioButton("demo")
        self._host_live = QRadioButton("live")
        self._host_group.addButton(self._host_demo)
        self._host_group.addButton(self._host_live)
        self._host_demo.setChecked(True)
        host_row = QWidget()
        host_layout = QHBoxLayout(host_row)
        host_layout.setContentsMargins(0, 0, 0, 0)
        host_layout.setSpacing(12)
        host_layout.addWidget(self._host_demo)
        host_layout.addWidget(self._host_live)
        host_layout.addStretch(1)
        layout.addRow(QLabel("Environment:"), host_row)
        
        # Client ID
        self.client_id = QLineEdit()
        self.client_id.setPlaceholderText("Enter Client ID")
        layout.addRow(QLabel("Client ID:"), self.client_id)
        
        # Client Secret
        self.client_secret = QLineEdit()
        self.client_secret.setPlaceholderText("Enter Client Secret")
        layout.addRow(QLabel("Client Secret:"), self.client_secret)
    
    def set_enabled(self, enabled: bool) -> None:
        """啟用或停用所有欄位"""
        if not self._host_locked:
            self.set_host_enabled(enabled)
        self.client_id.setEnabled(enabled)
        self.client_secret.setEnabled(enabled)

    def set_host_enabled(self, enabled: bool) -> None:
        """鎖定或解鎖Environment選擇"""
        self._host_locked = not enabled
        self._host_demo.setEnabled(enabled)
        self._host_live.setEnabled(enabled)

    def get_data(self) -> dict:
        """取得表單資料"""
        if self._host_live.isChecked():
            self._host_type = "live"
        else:
            self._host_type = "demo"
        return {
            "host_type": self._host_type,
            "client_id": self.client_id.text().strip(),
            "client_secret": self.client_secret.text().strip(),
        }
    
    def load_data(self, host: str, client_id: str, client_secret: str) -> None:
        """載入資料到表單"""
        if host in ("demo", "live"):
            self._host_type = host
            if host == "live":
                self._host_live.setChecked(True)
            else:
                self._host_demo.setChecked(True)
        self.client_id.setText(client_id)
        self.client_secret.setText(client_secret)
    
    def validate(self) -> Optional[str]:
        """驗證表單，回傳error訊息或 None"""
        data = self.get_data()
        if not data["client_id"]:
            return "Client ID is required"
        if not data["client_secret"]:
            return "Client Secret is required"
        return None


class AppAuthDialog(BaseAuthDialog):
    """cTrader app auth dialog"""
    
    # 訊號
    authSucceeded = Signal(object)  # 發送 Client
    authFailed = Signal(str)
    logReceived = Signal(str)
    statusChanged = Signal(int)

    def __init__(
        self, 
        token_file: str = TOKEN_FILE, 
        parent=None, 
        auto_connect: bool = False,
        app_auth_service: Optional[AppAuthServiceLike] = None,
        use_cases: Optional[BrokerUseCases] = None,
        event_bus: Optional[EventBus] = None,
        app_state: Optional[AppState] = None,
    ):
        super().__init__(token_file, parent, auto_connect, event_bus)
        self._service: Optional[AppAuthServiceLike] = app_auth_service
        self._use_cases: Optional[BrokerUseCases] = use_cases
        self._event_bus = event_bus
        self._app_state = app_state
        
        self._setup_ui()
        self._connect_signals()
        if self._service:
            self._service.set_callbacks(
                on_app_auth_success=lambda c: self.authSucceeded.emit(c),
                on_error=lambda e: self.authFailed.emit(e),
                on_log=lambda m: self.logReceived.emit(m),
                on_status_changed=lambda s: self.statusChanged.emit(int(s)),
            )
            self.statusChanged.emit(int(self._service.status))
        self._load_credentials()
        self._maybe_auto_start()

    def _setup_ui(self) -> None:
        """初始化 UI"""
        self.setWindowTitle("cTrader App Authentication")
        self.setMinimumSize(600, 350)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # 憑證表單
        self._form = CredentialsFormWidget()
        layout.addWidget(self._form)
        
        # Connect按鈕
        self._btn_connect = QPushButton("🔗 Connect")
        layout.addWidget(self._btn_connect)
        
        # 日誌區域
        self._log_widget = self._create_log_widget("Connection Log:")
        layout.addWidget(self._log_widget)
        
        # 彈性空間
        layout.addStretch()
        
        # Status指示器
        self._status_widget = self._create_status_widget()
        layout.addWidget(self._status_widget)

    def _connect_signals(self) -> None:
        """連接訊號"""
        self._btn_connect.clicked.connect(self._start_auth)
        self.authSucceeded.connect(self._handle_success)
        self.authFailed.connect(self._handle_error)
        self.statusChanged.connect(self._handle_status_changed)

    # ─────────────────────────────────────────────────────────────
    # 認證流程
    # ─────────────────────────────────────────────────────────────

    @Slot()
    def _start_auth(self) -> None:
        """Start認證流程"""
        if self._state.in_progress:
            return
        if self._service:
            if getattr(self._service, "status", None) == ConnectionStatus.CONNECTING:
                self._log_info("⏳ Connecting, please wait")
                return
            if getattr(self._service, "is_app_authenticated", False):
                self._log_info("App is already authenticated. No need to reconnect")
                self.accept()
                return

        # 驗證表單
        if error := self._form.validate():
            self._log_error(error)
            return
        
        data = self._form.get_data()
        
        # 儲存憑證
        if not self._save_credentials(data):
            return
        
        # 建立或重用服務
        if self._service is None:
            try:
                use_cases = self._use_cases
                if use_cases is None:
                    self._log_error(format_connection_message("missing_use_cases"))
                    return
                self._service = use_cases.create_app_auth(data["host_type"], self._token_file)
            except (FileNotFoundError, ValueError) as e:
                self._log_error(str(e))
                return

        self._state.in_progress = True
        self._set_controls_enabled(False)
        
        # 設定回調
        self._service.set_callbacks(
            on_app_auth_success=lambda c: self.authSucceeded.emit(c),
            on_error=lambda e: self.authFailed.emit(e),
            on_log=lambda m: self.logReceived.emit(m),
            on_status_changed=lambda s: self.statusChanged.emit(int(s)),
        )
        
        # 啟動Connect
        reactor_manager.ensure_running()
        
        from twisted.internet import reactor
        reactor.callFromThread(self._service.connect)

    # ─────────────────────────────────────────────────────────────
    # 槽函式
    # ─────────────────────────────────────────────────────────────

    @Slot(object)
    def _handle_success(self, client) -> None:
        """認證成功"""
        self._log_success("App authentication succeeded!")
        self.accept()

    @Slot(str)
    def _handle_error(self, error: str) -> None:
        """認證失敗"""
        self._log_error(error)
        self._set_controls_enabled(True)
        self._state.in_progress = False

    @Slot(int)
    def _handle_status_changed(self, status: int) -> None:
        """同步按鈕Status與認證Status"""
        if self._app_state:
            self._app_state.update_app_status(status)
        if self._event_bus:
            self._event_bus.publish("app_status", status)
        if status >= ConnectionStatus.APP_AUTHENTICATED:
            self._set_controls_enabled(False)
            return
        if not self._state.in_progress:
            self._set_controls_enabled(True)

    # ─────────────────────────────────────────────────────────────
    # 控制項Status
    # ─────────────────────────────────────────────────────────────

    def _set_controls_enabled(self, enabled: bool) -> None:
        """啟用或停用所有控制項"""
        self._form.set_enabled(enabled)
        self._btn_connect.setEnabled(enabled)

    # ─────────────────────────────────────────────────────────────
    # 憑證處理
    # ─────────────────────────────────────────────────────────────

    def _load_credentials(self) -> None:
        """從檔案載入憑證"""
        data = self._read_json_file()
        
        if not data:
            self._log_warning(f"Token file not found: {self._token_file}")
            self._form.set_host_enabled(True)
            return
        
        host = data.get("host_type", "demo")
        if host not in ("demo", "live"):
            self._log_warning(f"Invalid environment '{host}', falling back to demo")
            host = "demo"
        
        self._form.load_data(
            host=host,
            client_id=str(data.get("client_id", "")),
            client_secret=str(data.get("client_secret", "")),
        )
        # Token 已存在時鎖定Environment選擇
        self._form.set_host_enabled(False)

    def _save_credentials(self, data: dict) -> bool:
        """儲存憑證到檔案"""
        try:
            AppCredentials(
                host=data["host_type"],
                client_id=data["client_id"],
                client_secret=data["client_secret"],
            ).save(self._token_file)
            return True
        except Exception as e:
            self._log_error(f"Failed to save token file: {e}")
            return False

    # ─────────────────────────────────────────────────────────────
    # 公開 API
    # ─────────────────────────────────────────────────────────────

    def get_service(self) -> Optional[AppAuthServiceLike]:
        """取得認證後的服務實例"""
        return self._service
