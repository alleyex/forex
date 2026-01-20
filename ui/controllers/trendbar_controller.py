from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QObject

from application import AppAuthServiceLike, BrokerUseCases, OAuthServiceLike, TrendbarServiceLike
from config.constants import ConnectionStatus
from config.paths import TOKEN_FILE
from config.settings import OAuthTokens
from utils.reactor_manager import reactor_manager


class TrendbarController(QObject):
    def __init__(
        self,
        *,
        use_cases: BrokerUseCases,
        app_auth_service: AppAuthServiceLike,
        oauth_service: OAuthServiceLike,
        parent: QObject,
        log: Callable[[str], None],
        log_async: Callable[[str], None],
        set_active: Callable[[bool], None],
        format_price: Callable[[Optional[int]], str],
    ) -> None:
        super().__init__(parent)
        self._use_cases = use_cases
        self._app_auth_service = app_auth_service
        self._oauth_service = oauth_service
        self._log = log
        self._log_async = log_async
        self._set_active = set_active
        self._format_price = format_price
        self._trendbar_service: Optional[TrendbarServiceLike] = None
        self._active = False

    def toggle(self, symbol_id: int) -> None:
        if self._active:
            self.stop()
        else:
            self.start(symbol_id)

    def start(self, symbol_id: int) -> None:
        if not self._app_auth_service:
            self._log("⚠️ 尚未完成 App 認證")
            return
        if not self._is_app_authenticated():
            self._log("⚠️ App 認證已中斷，請稍候自動重連")
            return
        if not self._oauth_service or self._oauth_service.status != ConnectionStatus.ACCOUNT_AUTHENTICATED:
            self._log("⚠️ 尚未完成 OAuth 帳戶認證")
            return

        try:
            tokens = OAuthTokens.from_file(TOKEN_FILE)
        except Exception as exc:
            self._log(f"⚠️ 無法讀取 OAuth Token: {exc}")
            return
        if not tokens.account_id:
            self._log("⚠️ 缺少帳戶 ID")
            return

        if self._trendbar_service is None:
            self._trendbar_service = self._use_cases.create_trendbar(app_auth_service=self._app_auth_service)

        self._trendbar_service.clear_log_history()
        self._trendbar_service.set_callbacks(
            on_trendbar=lambda data: self._log_async(
                f"📊 M1 {data['timestamp']} "
                f"O={self._format_price(data['open'])} "
                f"H={self._format_price(data['high'])} "
                f"L={self._format_price(data['low'])} "
                f"C={self._format_price(data['close'])}"
            ),
            on_error=lambda e: self._log_async(f"⚠️ 趨勢棒錯誤: {e}"),
            on_log=self._log_async,
        )

        reactor_manager.ensure_running()
        from twisted.internet import reactor
        reactor.callFromThread(
            self._trendbar_service.subscribe,
            tokens.account_id,
            symbol_id,
        )
        self._active = True
        self._set_active(True)
        self._log(f"📈 已開始 M1 趨勢棒：symbol {symbol_id}")

    def stop(self) -> None:
        if not self._trendbar_service or not self._trendbar_service.in_progress:
            self._log("ℹ️ 目前沒有趨勢棒訂閱")
            self._active = False
            self._set_active(False)
            return
        reactor_manager.ensure_running()
        from twisted.internet import reactor
        reactor.callFromThread(self._trendbar_service.unsubscribe)
        self._active = False
        self._set_active(False)

    def reset(self) -> None:
        self._trendbar_service = None
        self._active = False
        self._set_active(False)

    def _is_app_authenticated(self) -> bool:
        is_auth = getattr(self._app_auth_service, "is_app_authenticated", None)
        if isinstance(is_auth, bool):
            return is_auth
        return self._app_auth_service.status >= ConnectionStatus.APP_AUTHENTICATED
