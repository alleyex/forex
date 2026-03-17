from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol

from forex.domain.accounts import Account, AccountFundsSnapshot


class AppAuthServiceLike(Protocol):
    status: int
    is_app_authenticated: bool

    def set_callbacks(
        self,
        on_app_auth_success=None,
        on_error=None,
        on_log=None,
        on_status_changed=None,
    ) -> None:
        ...

    def connect(self) -> None:
        ...

    def disconnect(self) -> None:
        ...

    def add_message_handler(self, handler) -> None:
        ...

    def remove_message_handler(self, handler) -> None:
        ...


class OAuthServiceLike(Protocol):
    status: int

    def set_callbacks(
        self,
        on_oauth_success=None,
        on_error=None,
        on_log=None,
        on_status_changed=None,
    ) -> None:
        ...

    def connect(self, timeout_seconds: int | None = None) -> None:
        ...

    def disconnect(self) -> None:
        ...


class OAuthLoginServiceLike(Protocol):
    def set_callbacks(self, on_oauth_login_success=None, on_error=None, on_log=None) -> None:
        ...

    def connect(self) -> None:
        ...

    def exchange_code(self, code: str):
        ...


class AccountListUseCaseLike(Protocol):
    in_progress: bool

    def set_access_token(self, access_token: str) -> None:
        ...

    def set_callbacks(
        self,
        on_accounts_received: Callable[[list[Account]], None] | None = None,
        on_error=None,
        on_log=None,
    ) -> None:
        ...

    def clear_log_history(self) -> None:
        ...

    def fetch(self, timeout_seconds: int | None = None) -> None:
        ...


class AccountFundsUseCaseLike(Protocol):
    in_progress: bool

    def set_callbacks(
        self,
        on_funds_received: Callable[[AccountFundsSnapshot], None] | None = None,
        on_position_pnl: Callable[[dict[int, float]], None] | None = None,
        on_error=None,
        on_log=None,
    ) -> None:
        ...

    def clear_log_history(self) -> None:
        ...

    def fetch(self, account_id: int, timeout_seconds: int | None = None) -> None:
        ...


class SymbolListUseCaseLike(Protocol):
    in_progress: bool

    def set_callbacks(self, on_symbols_received=None, on_error=None, on_log=None) -> None:
        ...

    def clear_log_history(self) -> None:
        ...

    def fetch(
        self,
        account_id: int,
        include_archived: bool = False,
        timeout_seconds: int | None = None,
    ) -> None:
        ...


class SymbolByIdUseCaseLike(Protocol):
    in_progress: bool

    def set_callbacks(self, on_symbols_received=None, on_error=None, on_log=None) -> None:
        ...

    def clear_log_history(self) -> None:
        ...

    def fetch(
        self,
        account_id: int,
        symbol_ids: Sequence[int],
        include_archived: bool = False,
        timeout_seconds: int | None = None,
    ) -> None:
        ...


class TrendbarServiceLike(Protocol):
    in_progress: bool

    def set_callbacks(self, on_trendbar=None, on_error=None, on_log=None) -> None:
        ...

    def clear_log_history(self) -> None:
        ...

    def subscribe(self, account_id: int, symbol_id: int, timeframe: str = "M1") -> None:
        ...

    def unsubscribe(self) -> None:
        ...


class TrendbarHistoryServiceLike(Protocol):
    def set_callbacks(self, on_history_received=None, on_error=None, on_log=None) -> None:
        ...

    def clear_log_history(self) -> None:
        ...

    def fetch(
        self,
        account_id: int,
        symbol_id: int,
        count: int = 100,
        timeframe: str = "M5",
        from_ts: int | None = None,
        to_ts: int | None = None,
    ) -> None:
        ...


class OrderServiceLike(Protocol):
    in_progress: bool

    def set_callbacks(self, on_execution=None, on_error=None, on_log=None) -> None:
        ...

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
        ...

    def close_position(self, *, account_id: int, position_id: int, volume: int) -> bool:
        ...


class DealHistoryServiceLike(Protocol):
    in_progress: bool

    def set_callbacks(self, on_deals_received=None, on_error=None, on_log=None) -> None:
        ...

    def clear_log_history(self) -> None:
        ...

    def fetch(
        self,
        account_id: int,
        *,
        max_rows: int = 15,
        to_timestamp: int | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        ...


class AccountFundsLike(Protocol):
    money_digits: int | None
    balance: float | None
    balance_version: int | None
    equity: float | None
    free_margin: float | None
    used_margin: float | None
    margin_level: float | None
    currency: str | None
    ctid_trader_account_id: int | None
    manager_bonus: float | None
    ib_bonus: float | None
    non_withdrawable_bonus: float | None
    access_rights: int | None
    deposit_asset_id: int | None
    swap_free: bool | None
    leverage_in_cents: int | None
    total_margin_calculation_type: int | None
    max_leverage: int | None
    french_risk: bool | None
    trader_login: int | None
    account_type: int | None
    broker_name: str | None
    registration_timestamp: int | None
    is_limited_risk: bool | None
    limited_risk_margin_calculation_strategy: int | None
    fair_stop_out: bool | None
    stop_out_strategy: int | None


class AccountProfileLike(Protocol):
    user_id: int | None


class CtidProfileUseCaseLike(Protocol):
    in_progress: bool

    def set_access_token(self, access_token: str) -> None:
        ...

    def set_callbacks(self, on_profile_received=None, on_error=None, on_log=None) -> None:
        ...

    def clear_log_history(self) -> None:
        ...

    def fetch(self, timeout_seconds: int | None = None) -> None:
        ...


class BrokerUseCaseFactory(Protocol):
    """Interface for creating broker-related services/use-cases."""

    def create_app_auth(self, host_type: str, token_file: str) -> AppAuthServiceLike:
        ...

    def create_oauth(
        self,
        app_auth_service: AppAuthServiceLike,
        token_file: str,
    ) -> OAuthServiceLike:
        ...

    def create_oauth_login(
        self, token_file: str, redirect_uri: str | None = None
    ) -> OAuthLoginServiceLike:
        ...

    def create_account_list_service(
        self, app_auth_service: AppAuthServiceLike, access_token: str
    ) -> AccountListUseCaseLike:
        ...

    def create_ctid_profile_service(
        self, app_auth_service: AppAuthServiceLike, access_token: str
    ) -> CtidProfileUseCaseLike:
        ...

    def create_account_funds_service(
        self,
        app_auth_service: AppAuthServiceLike,
    ) -> AccountFundsUseCaseLike:
        ...

    def create_symbol_list_service(
        self, app_auth_service: AppAuthServiceLike
    ) -> SymbolListUseCaseLike:
        ...

    def create_symbol_by_id_service(
        self, app_auth_service: AppAuthServiceLike
    ) -> SymbolByIdUseCaseLike:
        ...

    def create_trendbar_service(
        self,
        app_auth_service: AppAuthServiceLike,
    ) -> TrendbarServiceLike:
        ...

    def create_trendbar_history_service(
        self, app_auth_service: AppAuthServiceLike
    ) -> TrendbarHistoryServiceLike:
        ...

    def create_order_service(self, app_auth_service: AppAuthServiceLike) -> OrderServiceLike:
        ...

    def create_deal_history_service(
        self,
        app_auth_service: AppAuthServiceLike,
    ) -> DealHistoryServiceLike:
        ...
