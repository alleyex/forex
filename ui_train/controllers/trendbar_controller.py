from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QObject

from application import AppAuthServiceLike, BrokerUseCases, OAuthServiceLike, TrendbarServiceLike
from config.constants import ConnectionStatus
from config.paths import TOKEN_FILE
from config.settings import OAuthTokens
from utils.reactor_manager import reactor_manager
from ui_train.utils.formatters import format_trendbar_message


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
            self._log(format_trendbar_message("app_auth_missing"))
            return
        if not self._is_app_authenticated():
            self._log(format_trendbar_message("app_auth_disconnected"))
            return
        if not self._oauth_service or self._oauth_service.status != ConnectionStatus.ACCOUNT_AUTHENTICATED:
            self._log(format_trendbar_message("oauth_missing"))
            return

        try:
            tokens = OAuthTokens.from_file(TOKEN_FILE)
        except Exception as exc:
            self._log(format_trendbar_message("token_read_failed", error=exc))
            return
        if not tokens.account_id:
            self._log(format_trendbar_message("account_id_missing"))
            return

        if self._trendbar_service is None:
            self._trendbar_service = self._use_cases.create_trendbar(app_auth_service=self._app_auth_service)

        self._trendbar_service.clear_log_history()
        self._trendbar_service.set_callbacks(
            on_trendbar=lambda data: self._log_async(
                format_trendbar_message(
                    "trendbar_bar",
                    timeframe="M1",
                    timestamp=data["timestamp"],
                    open=self._format_price(data["open"]),
                    high=self._format_price(data["high"]),
                    low=self._format_price(data["low"]),
                    close=self._format_price(data["close"]),
                )
            ),
            on_error=lambda e: self._log_async(format_trendbar_message("trendbar_error", error=e)),
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
        self._log(format_trendbar_message("trendbar_started", symbol_id=symbol_id))

    def stop(self) -> None:
        if not self._trendbar_service or not self._trendbar_service.in_progress:
            self._log(format_trendbar_message("no_subscription"))
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
