"""
OAuth authentication dialog
"""
from dataclasses import dataclass
from typing import Optional

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFormLayout, QWidget, QSizePolicy, QDialog,
)
from PySide6.QtCore import Signal, Slot

from forex.ui.shared.dialogs.base_auth_dialog import BaseAuthDialog, DialogState
from forex.ui.shared.widgets.layout_helpers import configure_form_layout
from forex.domain.accounts import Account
from forex.application.broker.protocols import AppAuthServiceLike, OAuthLoginServiceLike, OAuthServiceLike
from forex.application.broker.use_cases import BrokerUseCases
from forex.application.events import EventBus
from forex.application.state import AppState
from forex.config.constants import ConnectionStatus
from forex.config.paths import TOKEN_FILE
from forex.config.settings import OAuthTokens
from forex.ui.shared.dialogs.account_dialog import AccountDialog
from forex.ui.shared.utils.formatters import format_connection_message
from forex.infrastructure.broker.ctrader.auth.refresh import refresh_tokens
from forex.utils.reactor_manager import reactor_manager


@dataclass
class OAuthDialogState(DialogState):
    """OAuth 對話框Status"""
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
        configure_form_layout(layout, horizontal_spacing=12, vertical_spacing=10)
        
        self.access_token = QLineEdit()
        self.access_token.setPlaceholderText("Enter access token")
        layout.addRow(QLabel("Access Token:"), self.access_token)
        
        self.refresh_token = QLineEdit()
        self.refresh_token.setPlaceholderText("Enter refresh token")
        layout.addRow(QLabel("Refresh Token:"), self.refresh_token)
        
        self.expires_at = QLineEdit()
        self.expires_at.setPlaceholderText("Unix timestamp or leave blank")
        layout.addRow(QLabel("Expires At:"), self.expires_at)
        
        self.account_id = QLineEdit()
        self.account_id.setPlaceholderText("CTID Trader Account ID")
        layout.addRow(QLabel("Account ID:"), self.account_id)
        
        self.redirect_uri = QLineEdit()
        self.redirect_uri.setPlaceholderText("http://127.0.0.1:8765/callback")
        layout.addRow(QLabel("Redirect URI:"), self.redirect_uri)
        
        self.auth_code = QLineEdit()
        self.auth_code.setPlaceholderText("Paste authorization code")
        layout.addRow(QLabel("Authorization Code:"), self.auth_code)
    
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
            return "Access Token is required"
        if not data["refresh_token"]:
            return "Refresh Token is required"
        if not data["account_id"]:
            return "Account ID is required"
        try:
            int(data["account_id"])
        except ValueError:
            return "Account ID must be numeric"
        return None
    
    def validate_for_login(self) -> Optional[str]:
        """驗證登入所需欄位"""
        data = self.get_data()
        if not data["redirect_uri"]:
            return "Redirect URI is required"
        return None


class OAuthDialog(BaseAuthDialog):
    """OAuth authentication dialog"""

    # 訊號
    authSucceeded = Signal(object)
    authFailed = Signal(str)
    logReceived = Signal(str)
    statusChanged = Signal(int)
    loginSucceeded = Signal(object)
    loginFailed = Signal(str)
    accountsReceived = Signal(list)
    accountsFailed = Signal(str)
    tokenRefreshSucceeded = Signal(object)
    tokenRefreshFailed = Signal(str)
    profileReceived = Signal(object)
    profileFailed = Signal(str)

    def __init__(
        self,
        token_file: str = TOKEN_FILE,
        parent=None,
        auto_connect: bool = False,
        app_auth_service: Optional[AppAuthServiceLike] = None,
        oauth_service: Optional[OAuthServiceLike] = None,
        use_cases: Optional[BrokerUseCases] = None,
        event_bus: Optional[EventBus] = None,
        app_state: Optional[AppState] = None,
    ):
        super().__init__(token_file, parent, auto_connect, event_bus)
        self._app_auth_service = app_auth_service
        self._use_cases: Optional[BrokerUseCases] = use_cases
        self._event_bus = event_bus
        self._app_state = app_state
        self._state = OAuthDialogState()
        self._auto_auth_after_accounts = False

        self._service: Optional[OAuthServiceLike] = oauth_service
        self._login_service: Optional[OAuthLoginServiceLike] = None
        self._selected_account: Optional[Account] = None

        self._setup_ui()
        self._connect_signals()
        if self._service:
            self._service.set_callbacks(
                on_oauth_success=lambda t: self.authSucceeded.emit(t),
                on_error=lambda e: self.authFailed.emit(e),
                on_log=lambda m: self.logReceived.emit(m),
                on_status_changed=lambda s: self.statusChanged.emit(int(s)),
            )
            self.statusChanged.emit(int(self._service.status))
        self._load_initial_data()
        self._maybe_auto_start()

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
        self._log_widget = self._create_log_widget("Connection Log:")
        layout.addWidget(self._log_widget)

        layout.addStretch()

        # Status指示器
        self._status_widget = self._create_status_widget()
        layout.addWidget(self._status_widget)

    def _create_button_layout(self) -> QHBoxLayout:
        """建立按鈕列"""
        layout = QHBoxLayout()
        
        self._btn_authorize = QPushButton("🌐 Authorize")
        self._btn_exchange_code = QPushButton("🔁 Exchange Code")
        self._btn_fetch_accounts = QPushButton("📥 Fetch Accounts")
        self._btn_connect = QPushButton("🔗 Connect")
        for btn in [
            self._btn_authorize,
            self._btn_exchange_code,
            self._btn_fetch_accounts,
            self._btn_connect,
        ]:
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

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
        self.tokenRefreshSucceeded.connect(self._handle_token_refresh_success)
        self.tokenRefreshFailed.connect(self._handle_token_refresh_error)
        self.profileReceived.connect(self._handle_profile_received)
        self.profileFailed.connect(self._handle_profile_error)
        self.statusChanged.connect(self._handle_status_changed)

    def _load_initial_data(self) -> None:
        """載入初始資料"""
        try:
            tokens = OAuthTokens.from_file(self._token_file)
            self._form.load_tokens(tokens)
            if tokens.account_id and self._selected_account is None:
                self._selected_account = Account(
                    account_id=int(tokens.account_id),
                    is_live=None,
                    trader_login=None,
                )
        except FileNotFoundError:
            self._log_warning(f"Token file not found: {self._token_file}")
        except Exception as exc:
            self._log_warning(f"Failed to load token: {exc}")

        if not self._form.redirect_uri.text().strip():
            self._form.redirect_uri.setText("http://127.0.0.1:8765/callback")

    # ─────────────────────────────────────────────────────────────
    # OAuth 流程
    # ─────────────────────────────────────────────────────────────

    @Slot()
    def _start_authorize(self) -> None:
        """Start OAuth 授權流程（自動取得授權碼）"""
        if self._state.login_in_progress:
            return

        if error := self._form.validate_for_login():
            self._log_error(error)
            return

        redirect_uri = self._form.redirect_uri.text().strip()

        try:
            if self._use_cases is None:
                self._log_error(format_connection_message("missing_use_cases"))
                return
            self._login_service = self._use_cases.create_oauth_login(
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
            self._log_error("Authorization code is required")
            return

        redirect_uri = self._form.redirect_uri.text().strip()
        try:
            if self._use_cases is None:
                self._log_error(format_connection_message("missing_use_cases"))
                return
            service = self._use_cases.create_oauth_login(
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
            self._log_error("Missing app authentication service")
            return

        if self._refresh_access_token_if_needed():
            return

        access_token = self._form.access_token.text().strip()
        if not access_token:
            self._log_error("Access Token is required")
            return

        if self._use_cases is None:
            self._log_error(format_connection_message("missing_use_cases"))
            return

        if self._use_cases.account_list_in_progress():
            self._log_info("⏳ Fetching account list, please wait")
            return

        self._set_accounts_busy(True)

        from twisted.internet import reactor
        reactor_manager.ensure_running()
        reactor.callFromThread(
            self._use_cases.fetch_accounts,
            self._app_auth_service,
            access_token,
            lambda a: self.accountsReceived.emit(a),
            lambda e: self.accountsFailed.emit(e),
            lambda m: self.logReceived.emit(m),
        )

    def _refresh_access_token_if_needed(self) -> bool:
        try:
            tokens = OAuthTokens.from_file(self._token_file)
        except Exception:
            return False
        if not tokens.is_expired():
            return False
        if not tokens.refresh_token:
            self._log_warning("⚠️ Access Token expired and no Refresh Token")
            return False

        self._set_accounts_busy(True)
        self._log_info("🔁 Access Token expired. Trying auto refresh...")

        import threading

        def run_refresh() -> None:
            try:
                refreshed = refresh_tokens(
                    token_file=self._token_file,
                    refresh_token=tokens.refresh_token,
                    existing_account_id=tokens.account_id,
                )
                refreshed.save(self._token_file)
                self.tokenRefreshSucceeded.emit(refreshed)
            except Exception as exc:
                self.tokenRefreshFailed.emit(str(exc))

        threading.Thread(target=run_refresh, daemon=True).start()
        return True

    @Slot()
    def _start_auth(self) -> None:
        """Start帳戶認證"""
        if self._state.auth_in_progress:
            return
        if self._service and self._service.status == ConnectionStatus.ACCOUNT_AUTHENTICATED:
            self._log_info("Account is already authorized. No reconnect needed")
            return

        if not self._app_auth_service:
            self._log_error("Missing app authentication service")
            return

        if not self._selected_account and not self._form.account_id.text().strip():
            access_token = self._form.access_token.text().strip()
            if access_token and self._use_cases and not self._state.accounts_in_progress:
                self._auto_auth_after_accounts = True
                self._log_info("🔎 Fetch account list first to complete selection")
                self._fetch_accounts()
                return

        if not self._form.account_id.text().strip():
            try:
                tokens = OAuthTokens.from_file(self._token_file)
                if tokens and tokens.account_id:
                    self._form.account_id.setText(str(tokens.account_id))
            except Exception:
                pass
        if not self._form.account_id.text().strip() and self._selected_account:
            self._form.account_id.setText(str(self._selected_account.account_id))

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
            if self._use_cases is None:
                self._log_error(format_connection_message("missing_use_cases"))
                return
            self._service = self._use_cases.create_oauth(self._app_auth_service, self._token_file)
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
        reactor_manager.ensure_running()
        reactor.callFromThread(self._service.connect)

    @Slot()
    # ─────────────────────────────────────────────────────────────
    # 槽函式
    # ─────────────────────────────────────────────────────────────

    @Slot(object)
    def _handle_auth_success(self, tokens: OAuthTokens) -> None:
        self._log_success("Account authentication succeeded!")
        self._state.auth_in_progress = False
        self._refresh_controls()
        self._fetch_ctid_profile(tokens.access_token)
        self.accept()

    @Slot(str)
    def _handle_auth_error(self, error: str) -> None:
        self._log_error(error)
        self._state.auth_in_progress = False
        self._refresh_controls()

    @Slot(object)
    def _handle_login_success(self, tokens: OAuthTokens) -> None:
        self._log_success("OAuth token acquired successfully")
        self._form.load_tokens(tokens)
        self._state.login_in_progress = False
        self._refresh_controls()
        if self._app_auth_service:
            self._fetch_accounts()
            self._fetch_ctid_profile(tokens.access_token)
        else:
            self._log_warning("Missing app authentication service, cannot fetch account list")

    @Slot(str)
    def _handle_login_error(self, error: str) -> None:
        self._log_error(error)
        self._log_info("ℹ️ If browser authorization fails, use 'Exchange Code' for manual login")
        self._state.login_in_progress = False
        self._refresh_controls()

    @Slot(int)
    def _handle_status_changed(self, status: int) -> None:
        if self._app_state:
            self._app_state.update_oauth_status(status)
        if self._event_bus:
            self._event_bus.publish("oauth_status", status)
        if status >= ConnectionStatus.ACCOUNT_AUTHENTICATED:
            if not self._state.auth_in_progress and not self._state.accounts_in_progress:
                if self._selected_account is None:
                    account_text = self._form.account_id.text().strip()
                    if account_text:
                        try:
                            self._selected_account = Account(
                                account_id=int(account_text),
                                is_live=None,
                                trader_login=None,
                            )
                        except (TypeError, ValueError):
                            self._selected_account = None
                if self._selected_account:
                    self.accept()

    @Slot(list)
    def _handle_accounts_received(self, accounts: list) -> None:
        self._log_success(f"Fetched account count: {len(accounts)}")
        try:
            tokens = OAuthTokens.from_file(self._token_file)
            if tokens and tokens.account_id:
                account_ids = {
                    int(a.account_id)
                    for a in accounts
                    if getattr(a, "account_id", None) is not None
                }
                if account_ids and int(tokens.account_id) not in account_ids:
                    self._log_warning(
                        f"Account mismatch：token={tokens.account_id}，available accounts={sorted(account_ids)}"
                    )
        except Exception:
            pass
        if len(accounts) == 1:
            self._selected_account = accounts[0]
            self._form.account_id.setText(str(accounts[0].account_id))
        elif len(accounts) > 1:
            dialog = AccountDialog(accounts, self)
            if dialog.exec() == QDialog.Accepted:
                selected = dialog.get_selected_account()
                if selected:
                    self._selected_account = selected
                    self._form.account_id.setText(str(selected.account_id))
            else:
                self._log_warning("Account selection cancelled")
        if self._selected_account:
            self._log_info(f"✅ Selected account: {self._selected_account.account_id}")
            if self._selected_account.permission_scope == 0:
                self._log_warning("⚠️ This account is view-only (SCOPE_VIEW), not tradable")
            try:
                tokens = OAuthTokens.from_file(self._token_file)
                if tokens:
                    tokens.account_id = int(self._selected_account.account_id)
                    tokens.save(self._token_file)
                    if self._service:
                        current_account = getattr(self._service.tokens, "account_id", None)
                        if current_account != tokens.account_id:
                            self._log_info(
                                f"🔁 Switch OAuth account {current_account} -> {tokens.account_id}"
                            )
                            self._service.update_tokens(tokens)
            except Exception:
                pass
        if self._auto_auth_after_accounts and self._selected_account:
            self._auto_auth_after_accounts = False
            self._start_auth()
        self._set_accounts_busy(False)
        if self._app_state:
            account_id = None if self._selected_account is None else self._selected_account.account_id
            scope = None if self._selected_account is None else self._selected_account.permission_scope
            self._app_state.set_selected_account(account_id, scope)

    @Slot(str)
    def _handle_accounts_error(self, error: str) -> None:
        self._log_error(error)
        self._set_accounts_busy(False)
        if self._auto_auth_after_accounts:
            self._auto_auth_after_accounts = False

    @Slot(object)
    def _handle_token_refresh_success(self, tokens: OAuthTokens) -> None:
        self._log_success("Access Token auto-refreshed")
        self._form.load_tokens(tokens)
        self._set_accounts_busy(False)
        self._fetch_accounts()

    @Slot(str)
    def _handle_token_refresh_error(self, error: str) -> None:
        self._log_error(f"Token refresh failed: {error}")
        self._set_accounts_busy(False)

    @Slot(object)
    def _handle_profile_received(self, profile) -> None:
        user_id = getattr(profile, "user_id", None)
        if user_id:
            self._log_info(f"🙋 CTID userId: {user_id}")
        else:
            self._log_info("🙋 CTID profile fetched")

    @Slot(str)
    def _handle_profile_error(self, error: str) -> None:
        self._log_warning(f"CTID profile fetch failed: {error}")

    def _fetch_ctid_profile(self, access_token: str) -> None:
        if not self._app_auth_service or not self._use_cases:
            return
        if self._use_cases.ctid_profile_in_progress():
            return
        if not access_token:
            return

        from twisted.internet import reactor
        reactor_manager.ensure_running()
        reactor.callFromThread(
            self._use_cases.fetch_ctid_profile,
            self._app_auth_service,
            access_token,
            lambda p: self.profileReceived.emit(p),
            lambda e: self.profileFailed.emit(e),
            lambda m: self.logReceived.emit(m),
        )

    def _set_accounts_busy(self, busy: bool) -> None:
        self._state.accounts_in_progress = busy
        self._refresh_controls()

    # ─────────────────────────────────────────────────────────────
    # 控制項Status
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
                raise ValueError("Expires-at must be numeric") from exc

        account_value = None
        if data["account_id"]:
            try:
                account_value = int(data["account_id"])
            except ValueError as exc:
                raise ValueError("Account ID must be numeric") from exc

        return OAuthTokens(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=expires_value,
            account_id=account_value,
        )

    # ─────────────────────────────────────────────────────────────
    # 公開 API
    # ─────────────────────────────────────────────────────────────

    def get_service(self) -> Optional[OAuthServiceLike]:
        """取得認證後的服務實例"""
        return self._service

    def get_selected_account(self) -> Optional[Account]:
        """取得已選擇的帳戶資訊"""
        return self._selected_account
