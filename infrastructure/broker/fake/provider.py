from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from broker.core.provider import BrokerProvider


@dataclass
class FakeAppAuthService:
    host_type: str
    token_file: str
    status: int = 0
    is_app_authenticated: bool = False

    def set_callbacks(self, on_app_auth_success=None, on_error=None, on_log=None, on_status_changed=None) -> None:
        self._on_app_auth_success = on_app_auth_success
        self._on_error = on_error
        self._on_log = on_log
        self._on_status_changed = on_status_changed

    def connect(self) -> None:
        self.is_app_authenticated = True
        if self._on_app_auth_success:
            self._on_app_auth_success(self)

    def disconnect(self) -> None:
        self.is_app_authenticated = False

    def add_message_handler(self, handler) -> None:
        pass

    def remove_message_handler(self, handler) -> None:
        pass


@dataclass
class FakeOAuthService:
    app_auth_service: FakeAppAuthService
    token_file: str
    status: int = 0

    def set_callbacks(self, on_oauth_success=None, on_error=None, on_log=None, on_status_changed=None) -> None:
        self._on_oauth_success = on_oauth_success
        self._on_error = on_error
        self._on_log = on_log
        self._on_status_changed = on_status_changed

    def connect(self, timeout_seconds: Optional[int] = None) -> None:
        if self._on_oauth_success:
            self._on_oauth_success(self)

    def disconnect(self) -> None:
        pass


@dataclass
class FakeOAuthLoginService:
    token_file: str
    redirect_uri: Optional[str]
    _on_oauth_login_success: Optional[callable] = None
    _on_error: Optional[callable] = None
    _on_log: Optional[callable] = None

    def set_callbacks(self, on_oauth_login_success=None, on_error=None, on_log=None) -> None:
        self._on_oauth_login_success = on_oauth_login_success
        self._on_error = on_error
        self._on_log = on_log

    def connect(self) -> None:
        if self._on_oauth_login_success:
            self._on_oauth_login_success(self)

    def exchange_code(self, code: str):
        return self


@dataclass
class FakeAccountListService:
    app_auth_service: FakeAppAuthService
    access_token: str
    in_progress: bool = False

    def set_access_token(self, access_token: str) -> None:
        self.access_token = access_token

    def set_callbacks(self, on_accounts_received=None, on_error=None, on_log=None) -> None:
        self._on_accounts_received = on_accounts_received
        self._on_error = on_error
        self._on_log = on_log

    def clear_log_history(self) -> None:
        pass

    def fetch(self, timeout_seconds: Optional[int] = None) -> None:
        if self._on_accounts_received:
            self._on_accounts_received([])


@dataclass
class FakeAccountFundsService:
    app_auth_service: FakeAppAuthService
    in_progress: bool = False
    balance: Optional[float] = None
    equity: Optional[float] = None
    free_margin: Optional[float] = None
    used_margin: Optional[float] = None
    margin_level: Optional[float] = None
    currency: Optional[str] = None
    money_digits: Optional[int] = None

    def set_callbacks(self, on_funds_received=None, on_error=None, on_log=None) -> None:
        self._on_funds_received = on_funds_received
        self._on_error = on_error
        self._on_log = on_log

    def clear_log_history(self) -> None:
        pass

    def fetch(self, account_id: int, timeout_seconds: Optional[int] = None) -> None:
        if self._on_funds_received:
            self._on_funds_received(self)


@dataclass
class FakeTrendbarService:
    app_auth_service: FakeAppAuthService
    in_progress: bool = False

    def set_callbacks(self, on_trendbar=None, on_error=None, on_log=None) -> None:
        self._on_trendbar = on_trendbar
        self._on_error = on_error
        self._on_log = on_log

    def clear_log_history(self) -> None:
        pass

    def subscribe(self, account_id: int, symbol_id: int, timeframe: str = "M1") -> None:
        pass

    def unsubscribe(self) -> None:
        pass


@dataclass
class FakeTrendbarHistoryService:
    app_auth_service: FakeAppAuthService

    def set_callbacks(self, on_history_received=None, on_error=None, on_log=None) -> None:
        self._on_history_received = on_history_received
        self._on_error = on_error
        self._on_log = on_log

    def clear_log_history(self) -> None:
        pass

    def fetch(
        self,
        account_id: int,
        symbol_id: int,
        count: int = 100000,
        timeframe: str = "M5",
        from_ts: Optional[int] = None,
        to_ts: Optional[int] = None,
    ) -> None:
        if self._on_history_received:
            self._on_history_received([])


@dataclass
class FakeSymbolListService:
    app_auth_service: FakeAppAuthService
    in_progress: bool = False

    def set_callbacks(self, on_symbols_received=None, on_error=None, on_log=None) -> None:
        self._on_symbols_received = on_symbols_received
        self._on_error = on_error
        self._on_log = on_log

    def clear_log_history(self) -> None:
        pass

    def fetch(
        self,
        account_id: int,
        include_archived: bool = False,
        timeout_seconds: Optional[int] = None,
    ) -> None:
        if self._on_symbols_received:
            self._on_symbols_received([])


class FakeProvider(BrokerProvider):
    """Fake provider for tests and offline development."""

    name = "fake"

    def create_app_auth(self, host_type: str, token_file: str):
        return FakeAppAuthService(host_type=host_type, token_file=token_file)

    def create_oauth(self, app_auth_service, token_file: str):
        return FakeOAuthService(app_auth_service=app_auth_service, token_file=token_file)

    def create_oauth_login(self, token_file: str, redirect_uri: Optional[str] = None):
        return FakeOAuthLoginService(token_file=token_file, redirect_uri=redirect_uri)

    def create_account_list_service(self, app_auth_service, access_token: str):
        return FakeAccountListService(app_auth_service=app_auth_service, access_token=access_token)

    def create_account_funds_service(self, app_auth_service):
        return FakeAccountFundsService(app_auth_service=app_auth_service)

    def create_symbol_list_service(self, app_auth_service):
        return FakeSymbolListService(app_auth_service=app_auth_service)

    def create_trendbar_service(self, app_auth_service):
        return FakeTrendbarService(app_auth_service=app_auth_service)

    def create_trendbar_history_service(self, app_auth_service):
        return FakeTrendbarHistoryService(app_auth_service=app_auth_service)
