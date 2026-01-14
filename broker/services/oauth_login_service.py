"""
OAuth 登入服務（瀏覽器流程）
"""
from dataclasses import dataclass
import threading
from typing import Callable, Optional, List

from broker.base import BaseCallbacks, LoggingMixin, OperationStateMixin, build_callbacks
from broker.oauth.tokens import TokenExchanger
from broker.oauth.callback_server import CallbackServer
from config.settings import OAuthTokens, AppCredentials


@dataclass
class OAuthLoginServiceCallbacks(BaseCallbacks):
    """OAuthLoginService 的回調函式"""
    on_oauth_login_success: Optional[Callable[[OAuthTokens], None]] = None


class OAuthLoginService(LoggingMixin[OAuthLoginServiceCallbacks], OperationStateMixin):
    """
    處理瀏覽器式 OAuth 授權碼流程

    使用方式：
        service = OAuthLoginService.create("token.json", "http://127.0.0.1:8765/callback")
        service.set_callbacks(on_oauth_login_success=..., on_error=...)
        service.connect()
    """

    def __init__(
        self,
        credentials: AppCredentials,
        redirect_uri: str,
        token_file: str,
    ):
        self._token_file = token_file
        self._token_exchanger = TokenExchanger(credentials, redirect_uri)
        self._callback_server = CallbackServer(redirect_uri)
        self._callbacks = OAuthLoginServiceCallbacks()
        self._in_progress = False
        self._log_history: List[str] = []

    @classmethod
    def create(cls, token_file: str, redirect_uri: str) -> "OAuthLoginService":
        """工廠方法：從設定檔建立服務實例"""
        credentials = AppCredentials.from_file(token_file)
        return cls(credentials=credentials, redirect_uri=redirect_uri, token_file=token_file)

    def set_callbacks(
        self,
        on_oauth_login_success: Optional[Callable[[OAuthTokens], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> None:
        """設定回調函式"""
        self._callbacks = build_callbacks(
            OAuthLoginServiceCallbacks,
            on_oauth_login_success=on_oauth_login_success,
            on_error=on_error,
            on_log=on_log,
        )
        if self._callbacks.on_log:
            for message in self._log_history:
                self._callbacks.on_log(message)

    def get_log_history(self) -> list[str]:
        return list(self._log_history)

    def _log(self, message: str) -> None:
        self._log_history.append(message)
        super()._log(message)

    def connect(self) -> None:
        """在背景執行緒中啟動 OAuth 流程"""
        if not self._start_operation():
            self._log("⚠️ 已有 OAuth 流程進行中")
            return
        thread = threading.Thread(target=self._run_flow, daemon=True)
        thread.start()

    def exchange_code(self, code: str) -> OAuthTokens:
        """將授權碼交換為 Token 並儲存"""
        existing_account_id = self._get_existing_account_id()
        tokens = self._token_exchanger.exchange_code(code, existing_account_id)
        tokens.save(self._token_file)
        return tokens

    def _run_flow(self) -> None:
        """執行完整的 OAuth 流程"""
        try:
            auth_url = self._token_exchanger.build_authorize_url()
            code = self._callback_server.wait_for_code(
                auth_url,
                timeout_seconds=300,
                on_log=self._log,
            )

            if not code:
                self._emit_error("OAuth 授權逾時")
                return

            tokens = self.exchange_code(code)
            self._log("✅ OAuth Token 已儲存")

            if self._callbacks.on_oauth_login_success:
                self._callbacks.on_oauth_login_success(tokens)
        except Exception as e:
            self._emit_error(str(e))
        finally:
            self._end_operation()

    def _get_existing_account_id(self) -> Optional[int]:
        """嘗試從 Token 檔案取得現有帳戶 ID"""
        try:
            existing = OAuthTokens.from_file(self._token_file)
            return existing.account_id
        except Exception:
            return None
