"""
OAuth 認證對話框
"""
from dataclasses import dataclass
from typing import Optional

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFormLayout, QWidget,
)
from PySide6.QtCore import Signal, Slot, Qt

from ui.dialogs.base_auth_dialog import BaseAuthDialog, DialogState
from broker.account import parse_accounts
from broker.oauth import OAuthService, OAuthLoginService, AccountListService
from broker.app_auth import AppAuthService
from config.constants import ConnectionStatus
from config.settings import OAuthTokens
from ui.dialogs.account_dialog import AccountDialog


@dataclass
class OAuthDialogState(DialogState):
    """OAuth 對話框狀態"""
    auth_in_progress: bool = False
    login_in_progress: bool = False
    accounts_in_progress: bool = False


class TokenFormWidget(QWidget):
    """Token 輸入表單元件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        layout = QFormLayout(self)
        layout.setLabelAlignment(Qt.AlignRight)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.access_token = QLineEdit()
        self.access_token.setPlaceholderText("輸入存取權杖")
        layout.addRow(QLabel("Access Token:"), self.access_token)
        
        self.refresh_token = QLineEdit()
        self.refresh_token.setPlaceholderText("輸入更新權杖")
        layout.addRow(QLabel("Refresh Token:"), self.refresh_token)
        
        self.expires_at = QLineEdit()
        self.expires_at.setPlaceholderText("Unix 時間戳記或留空")
        layout.addRow(QLabel("到期時間:"), self.expires_at)
        
        self.account_id = QLineEdit()
        self.account_id.setPlaceholderText("CTID 交易帳戶 ID")
        layout.addRow(QLabel("帳戶 ID:"), self.account_id)
        
        self.redirect_uri = QLineEdit()
        self.redirect_uri.setPlaceholderText("http://127.0.0.1:8765/callback")
        layout.addRow(QLabel("重導向 URI:"), self.redirect_uri)
        
        self.auth_code = QLineEdit()
        self.auth_code.setPlaceholderText("貼上授權碼")
        layout.addRow(QLabel("授權碼:"), self.auth_code)
    
    def set_enabled(self, enabled: bool) -> None:
        """啟用或停用所有欄位"""
        for field in [
            self.access_token, self.refresh_token, self.expires_at,
            self.account_id, self.redirect_uri, self.auth_code
        ]:
            field.setEnabled(enabled)
    
    def load_tokens(self, tokens: OAuthTokens) -> None:
        """載入 Token 到表單"""
        self.access_token.setText(tokens.access_token or "")
        self.refresh_token.setText(tokens.refresh_token or "")
        self.expires_at.setText("" if tokens.expires_at is None else str(tokens.expires_at))
        self.account_id.setText("" if tokens.account_id is None else str(tokens.account_id))
    
    def get_data(self) -> dict:
        """取得表單資料"""
        return {
            "access_token": self.access_token.text().strip(),
            "refresh_token": self.refresh_token.text().strip(),
            "expires_at": self.expires_at.text().strip(),
            "account_id": self.account_id.text().strip(),
            "redirect_uri": self.redirect_uri.text().strip(),
            "auth_code": self.auth_code.text().strip(),
        }
    
    def validate_for_auth(self) -> Optional[str]:
        """驗證認證所需欄位"""
        data = self.get_data()
        if not data["access_token"]:
            return "Access Token 為必填"
        if not data["refresh_token"]:
            return "Refresh Token 為必填"
        if not data["account_id"]:
            return "帳戶 ID 為必填"
        try:
            int(data["account_id"])
        except ValueError:
            return "帳戶 ID 必須是數字"
        return None
    
    def validate_for_login(self) -> Optional[str]:
        """驗證登入所需欄位"""
        data = self.get_data()
        if not data["redirect_uri"]:
            return "重導向 URI 為必填"
        return None


class OAuthDialog(BaseAuthDialog):
    """OAuth 認證對話框"""

    # 訊號
    authSucceeded = Signal(object)
    authFailed = Signal(str)
    logReceived = Signal(str)
    statusChanged = Signal(int)
    loginSucceeded = Signal(object)
    loginFailed = Signal(str)
    accountsReceived = Signal(list)
    accountsFailed = Signal(str)

    def __init__(
        self,
        token_file: str = "token.json",
        parent=None,
        auto_connect: bool = False,
        app_auth_service: Optional[AppAuthService] = None,
    ):
        super().__init__(token_file, parent, auto_connect)
        self._app_auth_service = app_auth_service
        self._state = OAuthDialogState()
        
        self._service: Optional[OAuthService] = None
        self._login_service: Optional[OAuthLoginService] = None
        self._account_list_service: Optional[AccountListService] = None

        self._setup_ui()
        self._connect_signals()
        self._load_initial_data()

    def _setup_ui(self) -> None:
        """初始化 UI"""
        self.setWindowTitle("cTrader OAuth")
        self.setMinimumSize(520, 340)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Token 表單
        self._form = TokenFormWidget()
        layout.addWidget(self._form)

        # 按鈕列
        layout.addLayout(self._create_button_layout())

        # 日誌區域
        self._log_widget = self._create_log_widget("連線日誌:")
        layout.addWidget(self._log_widget)

        layout.addStretch()

        # 狀態指示器
        self._status_widget = self._create_status_widget()
        layout.addWidget(self._status_widget)

    def _create_button_layout(self) -> QHBoxLayout:
        """建立按鈕列"""
        layout = QHBoxLayout()
        
        self._btn_authorize = QPushButton("🌐 授權")
        self._btn_exchange_code = QPushButton("🔁 交換授權碼")
        self._btn_fetch_accounts = QPushButton("📥 取得帳戶")
        self._btn_connect = QPushButton("🔗 連線")
        self._btn_connect.setMinimumHeight(40)

        layout.addWidget(self._btn_authorize)
        layout.addWidget(self._btn_exchange_code)
        layout.addWidget(self._btn_fetch_accounts)
        layout.addWidget(self._btn_connect)

        return layout

    def _connect_signals(self) -> None:
        """連接訊號"""
        self._btn_authorize.clicked.connect(self._start_authorize)
        self._btn_exchange_code.clicked.connect(self._exchange_auth_code)
        self._btn_fetch_accounts.clicked.connect(self._fetch_accounts)
        self._btn_connect.clicked.connect(self._start_auth)

        self.authSucceeded.connect(self._handle_auth_success)
        self.authFailed.connect(self._handle_auth_error)
        self.loginSucceeded.connect(self._handle_login_success)
        self.loginFailed.connect(self._handle_login_error)
        self.accountsReceived.connect(self._handle_accounts_received)
        self.accountsFailed.connect(self._handle_accounts_error)

    def _load_initial_data(self) -> None:
        """載入初始資料"""
        try:
            tokens = OAuthTokens.from_file(self._token_file)
            self._form.load_tokens(tokens)
        except FileNotFoundError:
            self._log_warning(f"找不到 Token 檔案: {self._token_file}")
        except Exception as exc:
            self._log_warning(f"載入 Token 失敗: {exc}")

        if not self._form.redirect_uri.text().strip():
            self._form.redirect_uri.setText("http://127.0.0.1:8765/callback")

    # ─────────────────────────────────────────────────────────────
    # OAuth 流程
    # ─────────────────────────────────────────────────────────────

    @Slot()
    def _start_authorize(self) -> None:
        """開始 OAuth 授權流程（自動取得授權碼）"""
        if self._state.login_in_progress:
            return

        if error := self._form.validate_for_login():
            self._log_error(error)
            return

        redirect_uri = self._form.redirect_uri.text().strip()

        try:
            self._login_service = OAuthLoginService.create(
                token_file=self._token_file,
                redirect_uri=redirect_uri,
            )
        except Exception as exc:
            self._log_error(str(exc))
            return

        self._login_service.set_callbacks(
            on_oauth_login_success=lambda t: self.loginSucceeded.emit(t),
            on_error=lambda e: self.loginFailed.emit(e),
            on_log=lambda m: self.logReceived.emit(m),
        )

        self._state.login_in_progress = True
        self._refresh_controls()
        self._login_service.connect()

    @Slot()
    def _exchange_auth_code(self) -> None:
        """交換授權碼取得 token"""
        if self._state.login_in_progress:
            return

        if error := self._form.validate_for_login():
            self._log_error(error)
            return

        code = self._form.auth_code.text().strip()
        if not code:
            self._log_error("授權碼為必填")
            return

        redirect_uri = self._form.redirect_uri.text().strip()
        try:
            service = OAuthLoginService.create(
                token_file=self._token_file,
                redirect_uri=redirect_uri,
            )
        except Exception as exc:
            self._log_error(str(exc))
            return

        self._state.login_in_progress = True
        self._refresh_controls()

        import threading

        def run_exchange() -> None:
            try:
                tokens = service.exchange_code(code)
                self.loginSucceeded.emit(tokens)
            except Exception as exc:
                self.loginFailed.emit(str(exc))

        threading.Thread(target=run_exchange, daemon=True).start()

    @Slot()
    def _fetch_accounts(self) -> None:
        """取得帳戶列表"""
        if self._state.accounts_in_progress:
            return

        if not self._app_auth_service:
            self._log_error("缺少應用程式認證服務")
            return

        access_token = self._form.access_token.text().strip()
        if not access_token:
            self._log_error("Access Token 為必填")
            return

        self._account_list_service = AccountListService(
            app_auth_service=self._app_auth_service,
            access_token=access_token,
        )
        self._account_list_service.set_callbacks(
            on_accounts_received=lambda a: self.accountsReceived.emit(a),
            on_error=lambda e: self.accountsFailed.emit(e),
            on_log=lambda m: self.logReceived.emit(m),
        )

        self._state.accounts_in_progress = True
        self._refresh_controls()

        from twisted.internet import reactor
        from utils.reactor_manager import reactor_manager
        reactor_manager.ensure_running()
        reactor.callFromThread(self._account_list_service.fetch)

    @Slot()
    def _start_auth(self) -> None:
        """開始帳戶認證"""
        if self._state.auth_in_progress:
            return

        if not self._app_auth_service:
            self._log_error("缺少應用程式認證服務")
            return

        if error := self._form.validate_for_auth():
            self._log_error(error)
            return

        try:
            tokens = self._build_tokens_from_form()
            tokens.save(self._token_file)
        except Exception as exc:
            self._log_error(str(exc))
            return

        try:
            self._service = OAuthService.create(self._app_auth_service, self._token_file)
        except Exception as exc:
            self._log_error(str(exc))
            return

        self._service.set_callbacks(
            on_oauth_success=lambda t: self.authSucceeded.emit(t),
            on_error=lambda e: self.authFailed.emit(e),
            on_log=lambda m: self.logReceived.emit(m),
            on_status_changed=lambda s: self.statusChanged.emit(int(s)),
        )

        self._state.auth_in_progress = True
        self._refresh_controls()

        from twisted.internet import reactor
        from utils.reactor_manager import reactor_manager
        reactor_manager.ensure_running()
        reactor.callFromThread(self._service.connect)

    # ─────────────────────────────────────────────────────────────
    # 槽函式
    # ─────────────────────────────────────────────────────────────

    @Slot(object)
    def _handle_auth_success(self, tokens: OAuthTokens) -> None:
        self._log_success("帳戶認證成功！")
        self._state.auth_in_progress = False
        self._refresh_controls()
        self.accept()

    @Slot(str)
    def _handle_auth_error(self, error: str) -> None:
        self._log_error(error)
        self._state.auth_in_progress = False
        self._refresh_controls()

    @Slot(object)
    def _handle_login_success(self, tokens: OAuthTokens) -> None:
        self._log_success("OAuth token 取得成功")
        self._form.load_tokens(tokens)
        self._state.login_in_progress = False
        self._refresh_controls()
        if self._app_auth_service:
            self._fetch_accounts()
        else:
            self._log_warning("缺少應用程式認證服務，無法取得帳戶列表")

    @Slot(str)
    def _handle_login_error(self, error: str) -> None:
        self._log_error(error)
        self._state.login_in_progress = False
        self._refresh_controls()

    @Slot(list)
    def _handle_accounts_received(self, accounts: list) -> None:
        parsed_accounts = parse_accounts(accounts)
        self._log_success(f"取得帳戶數: {len(parsed_accounts)}")
        if len(parsed_accounts) == 1:
            self._form.account_id.setText(str(parsed_accounts[0].account_id))
        elif len(parsed_accounts) > 1:
            dialog = AccountDialog(parsed_accounts, self)
            if dialog.exec() == dialog.Accepted:
                selected = dialog.get_selected_account()
                if selected:
                    self._form.account_id.setText(str(selected.account_id))
            else:
                self._log_warning("已取消帳戶選擇")
        self._state.accounts_in_progress = False
        self._refresh_controls()

    @Slot(str)
    def _handle_accounts_error(self, error: str) -> None:
        self._log_error(error)
        self._state.accounts_in_progress = False
        self._refresh_controls()

    # ─────────────────────────────────────────────────────────────
    # 控制項狀態
    # ─────────────────────────────────────────────────────────────

    def _refresh_controls(self) -> None:
        busy = (
            self._state.auth_in_progress
            or self._state.login_in_progress
            or self._state.accounts_in_progress
        )
        enabled = not busy
        self._form.set_enabled(enabled)
        self._btn_authorize.setEnabled(enabled)
        self._btn_exchange_code.setEnabled(enabled)
        self._btn_fetch_accounts.setEnabled(enabled)
        self._btn_connect.setEnabled(enabled)

    # ─────────────────────────────────────────────────────────────
    # 輔助方法
    # ─────────────────────────────────────────────────────────────

    def _build_tokens_from_form(self) -> OAuthTokens:
        data = self._form.get_data()

        expires_at = data["expires_at"]
        expires_value = None
        if expires_at:
            try:
                expires_value = int(expires_at)
            except ValueError as exc:
                raise ValueError("到期時間必須是數字") from exc

        account_value = None
        if data["account_id"]:
            try:
                account_value = int(data["account_id"])
            except ValueError as exc:
                raise ValueError("帳戶 ID 必須是數字") from exc

        return OAuthTokens(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=expires_value,
            account_id=account_value,
        )

    # ─────────────────────────────────────────────────────────────
    # 公開 API
    # ─────────────────────────────────────────────────────────────

    def get_service(self) -> Optional[OAuthService]:
        """取得認證後的服務實例"""
        return self._service
