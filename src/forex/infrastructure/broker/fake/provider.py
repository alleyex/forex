from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from forex.application.broker.provider import BrokerProvider
from forex.infrastructure.broker.base import BaseCallbacks, build_callbacks

Callback = Callable[..., None]


@dataclass
class FakeAppAuthCallbacks(BaseCallbacks):
    on_app_auth_success: Callback | None = None


@dataclass
class FakeOAuthCallbacks(BaseCallbacks):
    on_oauth_success: Callback | None = None


@dataclass
class FakeOAuthLoginCallbacks(BaseCallbacks):
    on_oauth_login_success: Callback | None = None


@dataclass
class FakeAccountListCallbacks(BaseCallbacks):
    on_accounts_received: Callback | None = None


@dataclass
class FakeCtidProfileCallbacks(BaseCallbacks):
    on_profile_received: Callback | None = None


@dataclass
class FakeAccountFundsCallbacks(BaseCallbacks):
    on_funds_received: Callback | None = None
    on_position_pnl: Callback | None = None


@dataclass
class FakeTrendbarCallbacks(BaseCallbacks):
    on_trendbar: Callback | None = None


@dataclass
class FakeTrendbarHistoryCallbacks(BaseCallbacks):
    on_history_received: Callback | None = None


@dataclass
class FakeSymbolsCallbacks(BaseCallbacks):
    on_symbols_received: Callback | None = None


@dataclass
class FakeOrderCallbacks(BaseCallbacks):
    on_execution: Callback | None = None


@dataclass
class FakeAppAuthService:
    host_type: str
    token_file: str
    status: int = 0
    is_app_authenticated: bool = False
    _callbacks: FakeAppAuthCallbacks = field(
        default_factory=FakeAppAuthCallbacks,
        repr=False,
    )

    def set_callbacks(
        self,
        on_app_auth_success=None,
        on_error=None,
        on_log=None,
        on_status_changed=None,
    ) -> None:
        self._callbacks = build_callbacks(
            FakeAppAuthCallbacks,
            on_app_auth_success=on_app_auth_success,
            on_error=on_error,
            on_log=on_log,
            on_status_changed=on_status_changed,
        )

    def connect(self) -> None:
        self.is_app_authenticated = True
        cb = self._callbacks.on_app_auth_success
        if cb:
            cb(self)

    def disconnect(self) -> None:
        self.is_app_authenticated = False

    def add_message_handler(self, handler) -> None:
        _ = handler

    def remove_message_handler(self, handler) -> None:
        _ = handler


@dataclass
class FakeOAuthService:
    app_auth_service: FakeAppAuthService
    token_file: str
    status: int = 0
    _callbacks: FakeOAuthCallbacks = field(
        default_factory=FakeOAuthCallbacks,
        repr=False,
    )

    def set_callbacks(
        self,
        on_oauth_success=None,
        on_error=None,
        on_log=None,
        on_status_changed=None,
    ) -> None:
        self._callbacks = build_callbacks(
            FakeOAuthCallbacks,
            on_oauth_success=on_oauth_success,
            on_error=on_error,
            on_log=on_log,
            on_status_changed=on_status_changed,
        )

    def connect(self, timeout_seconds: int | None = None) -> None:
        _ = timeout_seconds
        cb = self._callbacks.on_oauth_success
        if cb:
            cb(self)

    def disconnect(self) -> None:
        pass


@dataclass
class FakeOAuthLoginService:
    token_file: str
    redirect_uri: str | None
    _callbacks: FakeOAuthLoginCallbacks = field(default_factory=FakeOAuthLoginCallbacks, repr=False)

    def set_callbacks(self, on_oauth_login_success=None, on_error=None, on_log=None) -> None:
        self._callbacks = build_callbacks(
            FakeOAuthLoginCallbacks,
            on_oauth_login_success=on_oauth_login_success,
            on_error=on_error,
            on_log=on_log,
        )

    def connect(self) -> None:
        cb = self._callbacks.on_oauth_login_success
        if cb:
            cb(self)

    def exchange_code(self, code: str):
        _ = code
        return self


@dataclass
class FakeAccountListService:
    app_auth_service: FakeAppAuthService
    access_token: str
    in_progress: bool = False
    _callbacks: FakeAccountListCallbacks = field(
        default_factory=FakeAccountListCallbacks,
        repr=False,
    )

    def set_access_token(self, access_token: str) -> None:
        self.access_token = access_token

    def set_callbacks(self, on_accounts_received=None, on_error=None, on_log=None) -> None:
        self._callbacks = build_callbacks(
            FakeAccountListCallbacks,
            on_accounts_received=on_accounts_received,
            on_error=on_error,
            on_log=on_log,
        )

    def clear_log_history(self) -> None:
        pass

    def fetch(self, timeout_seconds: int | None = None) -> None:
        _ = timeout_seconds
        cb = self._callbacks.on_accounts_received
        if cb:
            cb([])


@dataclass
class FakeCtidProfileService:
    app_auth_service: FakeAppAuthService
    access_token: str
    in_progress: bool = False
    user_id: int | None = None
    _callbacks: FakeCtidProfileCallbacks = field(
        default_factory=FakeCtidProfileCallbacks,
        repr=False,
    )

    def set_access_token(self, access_token: str) -> None:
        self.access_token = access_token

    def set_callbacks(self, on_profile_received=None, on_error=None, on_log=None) -> None:
        self._callbacks = build_callbacks(
            FakeCtidProfileCallbacks,
            on_profile_received=on_profile_received,
            on_error=on_error,
            on_log=on_log,
        )

    def clear_log_history(self) -> None:
        pass

    def fetch(self, timeout_seconds: int | None = None) -> None:
        _ = timeout_seconds
        cb = self._callbacks.on_profile_received
        if cb:
            cb(self)


@dataclass
class FakeAccountFundsService:
    app_auth_service: FakeAppAuthService
    in_progress: bool = False
    balance: float | None = None
    balance_version: int | None = None
    equity: float | None = None
    free_margin: float | None = None
    used_margin: float | None = None
    margin_level: float | None = None
    currency: str | None = None
    money_digits: int | None = None
    ctid_trader_account_id: int | None = None
    manager_bonus: float | None = None
    ib_bonus: float | None = None
    non_withdrawable_bonus: float | None = None
    access_rights: int | None = None
    deposit_asset_id: int | None = None
    swap_free: bool | None = None
    leverage_in_cents: int | None = None
    total_margin_calculation_type: int | None = None
    max_leverage: int | None = None
    french_risk: bool | None = None
    trader_login: int | None = None
    account_type: int | None = None
    broker_name: str | None = None
    registration_timestamp: int | None = None
    is_limited_risk: bool | None = None
    limited_risk_margin_calculation_strategy: int | None = None
    fair_stop_out: bool | None = None
    stop_out_strategy: int | None = None
    _callbacks: FakeAccountFundsCallbacks = field(
        default_factory=FakeAccountFundsCallbacks,
        repr=False,
    )

    def set_callbacks(
        self,
        on_funds_received=None,
        on_position_pnl=None,
        on_error=None,
        on_log=None,
    ) -> None:
        self._callbacks = build_callbacks(
            FakeAccountFundsCallbacks,
            on_funds_received=on_funds_received,
            on_position_pnl=on_position_pnl,
            on_error=on_error,
            on_log=on_log,
        )

    def clear_log_history(self) -> None:
        pass

    def fetch(self, account_id: int, timeout_seconds: int | None = None) -> None:
        _ = account_id, timeout_seconds
        cb = self._callbacks.on_funds_received
        if cb:
            cb(self)


@dataclass
class FakeTrendbarService:
    app_auth_service: FakeAppAuthService
    in_progress: bool = False
    _callbacks: FakeTrendbarCallbacks = field(default_factory=FakeTrendbarCallbacks, repr=False)

    def set_callbacks(self, on_trendbar=None, on_error=None, on_log=None) -> None:
        self._callbacks = build_callbacks(
            FakeTrendbarCallbacks,
            on_trendbar=on_trendbar,
            on_error=on_error,
            on_log=on_log,
        )

    def clear_log_history(self) -> None:
        pass

    def subscribe(self, account_id: int, symbol_id: int, timeframe: str = "M1") -> None:
        _ = account_id, symbol_id, timeframe

    def unsubscribe(self) -> None:
        pass


@dataclass
class FakeTrendbarHistoryService:
    app_auth_service: FakeAppAuthService
    _callbacks: FakeTrendbarHistoryCallbacks = field(
        default_factory=FakeTrendbarHistoryCallbacks,
        repr=False,
    )

    def set_callbacks(self, on_history_received=None, on_error=None, on_log=None) -> None:
        self._callbacks = build_callbacks(
            FakeTrendbarHistoryCallbacks,
            on_history_received=on_history_received,
            on_error=on_error,
            on_log=on_log,
        )

    def clear_log_history(self) -> None:
        pass

    def fetch(
        self,
        account_id: int,
        symbol_id: int,
        count: int = 100000,
        timeframe: str = "M5",
        from_ts: int | None = None,
        to_ts: int | None = None,
    ) -> None:
        _ = account_id, symbol_id, count, timeframe, from_ts, to_ts
        cb = self._callbacks.on_history_received
        if cb:
            cb([])


@dataclass
class FakeSymbolListService:
    app_auth_service: FakeAppAuthService
    in_progress: bool = False
    _callbacks: FakeSymbolsCallbacks = field(default_factory=FakeSymbolsCallbacks, repr=False)

    def set_callbacks(self, on_symbols_received=None, on_error=None, on_log=None) -> None:
        self._callbacks = build_callbacks(
            FakeSymbolsCallbacks,
            on_symbols_received=on_symbols_received,
            on_error=on_error,
            on_log=on_log,
        )

    def clear_log_history(self) -> None:
        pass

    def fetch(
        self,
        account_id: int,
        include_archived: bool = False,
        timeout_seconds: int | None = None,
    ) -> None:
        _ = account_id, include_archived, timeout_seconds
        cb = self._callbacks.on_symbols_received
        if cb:
            cb([])


@dataclass
class FakeSymbolByIdService:
    app_auth_service: FakeAppAuthService
    in_progress: bool = False
    _callbacks: FakeSymbolsCallbacks = field(default_factory=FakeSymbolsCallbacks, repr=False)

    def set_callbacks(self, on_symbols_received=None, on_error=None, on_log=None) -> None:
        self._callbacks = build_callbacks(
            FakeSymbolsCallbacks,
            on_symbols_received=on_symbols_received,
            on_error=on_error,
            on_log=on_log,
        )

    def clear_log_history(self) -> None:
        pass

    def fetch(
        self,
        account_id: int,
        symbol_ids: list[int],
        include_archived: bool = False,
        timeout_seconds: int | None = None,
    ) -> None:
        _ = account_id, symbol_ids, include_archived, timeout_seconds
        cb = self._callbacks.on_symbols_received
        if cb:
            cb([])


@dataclass
class FakeOrderService:
    app_auth_service: FakeAppAuthService
    in_progress: bool = False
    _permission_scope: int | None = None
    _callbacks: FakeOrderCallbacks = field(default_factory=FakeOrderCallbacks, repr=False)

    def set_callbacks(self, on_execution=None, on_error=None, on_log=None) -> None:
        self._callbacks = build_callbacks(
            FakeOrderCallbacks,
            on_execution=on_execution,
            on_error=on_error,
            on_log=on_log,
        )

    def set_permission_scope(self, scope: int | None) -> None:
        self._permission_scope = None if scope is None else int(scope)

    def place_market_order(
        self,
        *,
        account_id: int,
        symbol_id: int,
        trade_side: str,
        volume: int,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        label: str | None = None,
        comment: str | None = None,
        client_order_id: str | None = None,
        slippage_points: int | None = None,
    ) -> str | None:
        _ = (
            account_id,
            symbol_id,
            trade_side,
            volume,
            stop_loss,
            take_profit,
            label,
            comment,
            slippage_points,
        )
        cb = self._callbacks.on_execution
        if cb:
            cb(
                {
                    "client_order_id": client_order_id,
                    "position_id": None,
                    "order": None,
                    "position": None,
                    "deal": None,
                }
            )
        return client_order_id

    def close_position(self, *, account_id: int, position_id: int, volume: int) -> bool:
        _ = account_id, volume
        cb = self._callbacks.on_execution
        if cb:
            cb(
                {
                    "client_order_id": None,
                    "position_id": position_id,
                    "order": None,
                    "position": None,
                    "deal": None,
                }
            )
        return True


class FakeProvider(BrokerProvider):
    """Fake provider for tests and offline development."""

    name = "fake"

    def create_app_auth(self, host_type: str, token_file: str):
        return FakeAppAuthService(host_type=host_type, token_file=token_file)

    def create_oauth(self, app_auth_service, token_file: str):
        return FakeOAuthService(app_auth_service=app_auth_service, token_file=token_file)

    def create_oauth_login(self, token_file: str, redirect_uri: str | None = None):
        return FakeOAuthLoginService(token_file=token_file, redirect_uri=redirect_uri)

    def create_account_list_service(self, app_auth_service, access_token: str):
        return FakeAccountListService(app_auth_service=app_auth_service, access_token=access_token)

    def create_ctid_profile_service(self, app_auth_service, access_token: str):
        return FakeCtidProfileService(app_auth_service=app_auth_service, access_token=access_token)

    def create_account_funds_service(self, app_auth_service):
        return FakeAccountFundsService(app_auth_service=app_auth_service)

    def create_symbol_list_service(self, app_auth_service):
        return FakeSymbolListService(app_auth_service=app_auth_service)

    def create_symbol_by_id_service(self, app_auth_service):
        return FakeSymbolByIdService(app_auth_service=app_auth_service)

    def create_trendbar_service(self, app_auth_service):
        return FakeTrendbarService(app_auth_service=app_auth_service)

    def create_trendbar_history_service(self, app_auth_service):
        return FakeTrendbarHistoryService(app_auth_service=app_auth_service)

    def create_order_service(self, app_auth_service):
        return FakeOrderService(app_auth_service=app_auth_service)
