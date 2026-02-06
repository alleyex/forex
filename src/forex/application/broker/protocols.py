from __future__ import annotations

from typing import Callable, Optional, Protocol, Sequence

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

    def connect(self, timeout_seconds: Optional[int] = None) -> None:
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
        on_accounts_received: Optional[Callable[[list[Account]], None]] = None,
        on_error=None,
        on_log=None,
    ) -> None:
        ...

    def clear_log_history(self) -> None:
        ...

    def fetch(self, timeout_seconds: Optional[int] = None) -> None:
        ...


class AccountFundsUseCaseLike(Protocol):
    in_progress: bool

    def set_callbacks(
        self,
        on_funds_received: Optional[Callable[[AccountFundsSnapshot], None]] = None,
        on_position_pnl: Optional[Callable[[dict[int, float]], None]] = None,
        on_error=None,
        on_log=None,
    ) -> None:
        ...

    def clear_log_history(self) -> None:
        ...

    def fetch(self, account_id: int, timeout_seconds: Optional[int] = None) -> None:
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
        timeout_seconds: Optional[int] = None,
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
        timeout_seconds: Optional[int] = None,
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
        from_ts: Optional[int] = None,
        to_ts: Optional[int] = None,
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
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        label: Optional[str] = None,
        comment: Optional[str] = None,
        client_order_id: Optional[str] = None,
        slippage_points: Optional[int] = None,
    ) -> Optional[str]:
        ...

    def close_position(self, *, account_id: int, position_id: int, volume: int) -> bool:
        ...


class AccountFundsLike(Protocol):
    money_digits: Optional[int]
    balance: Optional[float]
    equity: Optional[float]
    free_margin: Optional[float]
    used_margin: Optional[float]
    margin_level: Optional[float]
    currency: Optional[str]


class BrokerUseCaseFactory(Protocol):
    """Interface for creating broker-related services/use-cases."""

    def create_app_auth(self, host_type: str, token_file: str) -> AppAuthServiceLike:
        ...

    def create_oauth(self, app_auth_service: AppAuthServiceLike, token_file: str) -> OAuthServiceLike:
        ...

    def create_oauth_login(
        self, token_file: str, redirect_uri: Optional[str] = None
    ) -> OAuthLoginServiceLike:
        ...

    def create_account_list_service(
        self, app_auth_service: AppAuthServiceLike, access_token: str
    ) -> AccountListUseCaseLike:
        ...

    def create_account_funds_service(self, app_auth_service: AppAuthServiceLike) -> AccountFundsUseCaseLike:
        ...

    def create_symbol_list_service(
        self, app_auth_service: AppAuthServiceLike
    ) -> SymbolListUseCaseLike:
        ...

    def create_symbol_by_id_service(
        self, app_auth_service: AppAuthServiceLike
    ) -> SymbolByIdUseCaseLike:
        ...

    def create_trendbar_service(self, app_auth_service: AppAuthServiceLike) -> TrendbarServiceLike:
        ...

    def create_trendbar_history_service(
        self, app_auth_service: AppAuthServiceLike
    ) -> TrendbarHistoryServiceLike:
        ...

    def create_order_service(self, app_auth_service: AppAuthServiceLike) -> OrderServiceLike:
        ...
