from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QObject

from application.broker.protocols import AppAuthServiceLike, OAuthServiceLike, TrendbarServiceLike
from application.broker.use_cases import BrokerUseCases
from config.constants import ConnectionStatus
from config.paths import TOKEN_FILE
from config.settings import OAuthTokens
from utils.reactor_manager import reactor_manager
from ui.train.presenters.trendbar_presenter import TrendbarPresenter


class TrendbarController(QObject):
    def __init__(
        self,
        *,
        use_cases: BrokerUseCases,
        app_auth_service: AppAuthServiceLike,
        oauth_service: OAuthServiceLike,
        parent: QObject,
        presenter: TrendbarPresenter,
        format_price: Callable[[Optional[int]], str],
    ) -> None:
        super().__init__(parent)
        self._use_cases = use_cases
        self._app_auth_service = app_auth_service
        self._oauth_service = oauth_service
        self._presenter = presenter
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
            self._presenter.log_event("app_auth_missing")
            return
        if not self._is_app_authenticated():
            self._presenter.log_event("app_auth_disconnected")
            return
        if not self._oauth_service or self._oauth_service.status != ConnectionStatus.ACCOUNT_AUTHENTICATED:
            self._presenter.log_event("oauth_missing")
            return

        try:
            tokens = OAuthTokens.from_file(TOKEN_FILE)
        except Exception as exc:
            self._presenter.log_event("token_read_failed", error=exc)
            return
        if not tokens.account_id:
            self._presenter.log_event("account_id_missing")
            return

        if self._trendbar_service is None:
            self._trendbar_service = self._use_cases.create_trendbar(app_auth_service=self._app_auth_service)

        self._trendbar_service.clear_log_history()
        self._trendbar_service.set_callbacks(
            on_trendbar=lambda data: self._presenter.log_event(
                "trendbar_bar",
                timeframe="M1",
                timestamp=data["timestamp"],
                open=self._format_price(data["open"]),
                high=self._format_price(data["high"]),
                low=self._format_price(data["low"]),
                close=self._format_price(data["close"]),
            ),
            on_error=lambda e: self._presenter.log_event("trendbar_error", error=e),
            on_log=self._presenter.log_raw,
        )

        reactor_manager.ensure_running()
        from twisted.internet import reactor
        reactor.callFromThread(
            self._trendbar_service.subscribe,
            tokens.account_id,
            symbol_id,
        )
        self._active = True
        self._presenter.set_active(True)
        self._presenter.log_event("trendbar_started", symbol_id=symbol_id)

    def stop(self) -> None:
        if not self._trendbar_service or not self._trendbar_service.in_progress:
            self._presenter.log_event("no_subscription")
            self._active = False
            self._presenter.set_active(False)
            return
        reactor_manager.ensure_running()
        from twisted.internet import reactor
        reactor.callFromThread(self._trendbar_service.unsubscribe)
        self._active = False
        self._presenter.set_active(False)

    def reset(self) -> None:
        self._trendbar_service = None
        self._active = False
        self._presenter.set_active(False)

    def _is_app_authenticated(self) -> bool:
        is_auth = getattr(self._app_auth_service, "is_app_authenticated", None)
        if isinstance(is_auth, bool):
            return is_auth
        return self._app_auth_service.status >= ConnectionStatus.APP_AUTHENTICATED
