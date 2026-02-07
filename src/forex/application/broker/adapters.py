from __future__ import annotations

from typing import Iterable, Optional, Protocol

from forex.application.broker.protocols import (
    AccountFundsLike,
    AccountFundsUseCaseLike,
    AccountListUseCaseLike,
    AccountProfileLike,
    CtidProfileUseCaseLike,
    SymbolByIdUseCaseLike,
    SymbolListUseCaseLike,
)
from forex.domain.accounts import Account, AccountFundsSnapshot, AccountProfile
from forex.domain.symbols import Symbol


class AccountInfoLike(Protocol):
    account_id: int
    is_live: Optional[bool]
    trader_login: Optional[int]
    permission_scope: Optional[int]
    last_closing_deal_timestamp: Optional[int]
    last_balance_update_timestamp: Optional[int]

class SymbolInfoLike(Protocol):
    symbol_id: int
    symbol_name: str


def to_account(info: AccountInfoLike) -> Account:
    return Account(
        account_id=int(info.account_id),
        is_live=info.is_live,
        trader_login=info.trader_login,
        permission_scope=getattr(info, "permission_scope", None),
        last_closing_deal_timestamp=getattr(info, "last_closing_deal_timestamp", None),
        last_balance_update_timestamp=getattr(info, "last_balance_update_timestamp", None),
    )


def to_accounts(infos: Iterable[AccountInfoLike]) -> list[Account]:
    return [to_account(info) for info in infos]


def to_accounts_from_dicts(raw_accounts: Iterable[dict]) -> list[Account]:
    accounts: list[Account] = []
    for item in raw_accounts:
        try:
            accounts.append(
                Account(
                    account_id=int(item.get("account_id", 0)),
                    is_live=bool(item.get("is_live", False)) if item.get("is_live") is not None else None,
                    trader_login=item.get("trader_login"),
                    permission_scope=item.get("permission_scope"),
                    last_closing_deal_timestamp=item.get("last_closing_deal_timestamp"),
                    last_balance_update_timestamp=item.get("last_balance_update_timestamp"),
                )
            )
        except Exception:
            continue
    return accounts


def to_funds_snapshot(funds: AccountFundsLike) -> AccountFundsSnapshot:
    return AccountFundsSnapshot(
        balance=funds.balance,
        balance_version=funds.balance_version,
        equity=funds.equity,
        free_margin=funds.free_margin,
        used_margin=funds.used_margin,
        margin_level=funds.margin_level,
        currency=funds.currency,
        money_digits=funds.money_digits,
        ctid_trader_account_id=funds.ctid_trader_account_id,
        manager_bonus=funds.manager_bonus,
        ib_bonus=funds.ib_bonus,
        non_withdrawable_bonus=funds.non_withdrawable_bonus,
        access_rights=funds.access_rights,
        deposit_asset_id=funds.deposit_asset_id,
        swap_free=funds.swap_free,
        leverage_in_cents=funds.leverage_in_cents,
        total_margin_calculation_type=funds.total_margin_calculation_type,
        max_leverage=funds.max_leverage,
        french_risk=funds.french_risk,
        trader_login=funds.trader_login,
        account_type=funds.account_type,
        broker_name=funds.broker_name,
        registration_timestamp=funds.registration_timestamp,
        is_limited_risk=funds.is_limited_risk,
        limited_risk_margin_calculation_strategy=funds.limited_risk_margin_calculation_strategy,
        fair_stop_out=funds.fair_stop_out,
        stop_out_strategy=funds.stop_out_strategy,
    )


def to_profile(profile: AccountProfileLike) -> AccountProfile:
    return AccountProfile(user_id=getattr(profile, "user_id", None))


def to_symbol(info: SymbolInfoLike) -> Symbol:
    return Symbol(symbol_id=int(info.symbol_id), name=str(info.symbol_name))


def to_symbols(infos: Iterable[SymbolInfoLike]) -> list[Symbol]:
    return [to_symbol(info) for info in infos]


def to_symbols_from_dicts(raw_symbols: Iterable[dict]) -> list[Symbol]:
    symbols: list[Symbol] = []
    for item in raw_symbols:
        try:
            symbols.append(
                Symbol(
                    symbol_id=int(item.get("symbol_id", 0)),
                    name=str(item.get("symbol_name", "")),
                )
            )
        except Exception:
            continue
    return symbols


class AccountListServiceAdapter:
    def __init__(self, service: AccountListUseCaseLike):
        self._service = service

    @property
    def in_progress(self) -> bool:
        return self._service.in_progress

    def set_access_token(self, access_token: str) -> None:
        self._service.set_access_token(access_token)

    def set_callbacks(self, on_accounts_received=None, on_error=None, on_log=None) -> None:
        def handle_accounts(raw_accounts) -> None:
            domain_accounts = to_accounts_from_dicts(raw_accounts)
            if on_accounts_received:
                on_accounts_received(domain_accounts)

        self._service.set_callbacks(
            on_accounts_received=handle_accounts,
            on_error=on_error,
            on_log=on_log,
        )

    def clear_log_history(self) -> None:
        self._service.clear_log_history()

    def fetch(self, timeout_seconds: Optional[int] = None) -> None:
        self._service.fetch(timeout_seconds)


class AccountFundsServiceAdapter:
    def __init__(self, service: AccountFundsUseCaseLike):
        self._service = service

    @property
    def in_progress(self) -> bool:
        return self._service.in_progress

    def set_callbacks(self, on_funds_received=None, on_position_pnl=None, on_error=None, on_log=None) -> None:
        def handle_funds(funds: AccountFundsLike) -> None:
            snapshot = to_funds_snapshot(funds)
            if on_funds_received:
                on_funds_received(snapshot)

        self._service.set_callbacks(
            on_funds_received=handle_funds,
            on_position_pnl=on_position_pnl,
            on_error=on_error,
            on_log=on_log,
        )

    def clear_log_history(self) -> None:
        self._service.clear_log_history()

    def fetch(self, account_id: int, timeout_seconds: Optional[int] = None) -> None:
        self._service.fetch(account_id, timeout_seconds)


class SymbolListServiceAdapter:
    def __init__(self, service: SymbolListUseCaseLike):
        self._service = service

    @property
    def in_progress(self) -> bool:
        return self._service.in_progress

    def set_callbacks(self, on_symbols_received=None, on_error=None, on_log=None) -> None:
        def handle_symbols(raw_symbols) -> None:
            if on_symbols_received:
                on_symbols_received(raw_symbols)

        self._service.set_callbacks(
            on_symbols_received=handle_symbols,
            on_error=on_error,
            on_log=on_log,
        )

    def clear_log_history(self) -> None:
        self._service.clear_log_history()

    def fetch(
        self,
        account_id: int,
        include_archived: bool = False,
        timeout_seconds: Optional[int] = None,
    ) -> None:
        self._service.fetch(
            account_id=account_id,
            include_archived=include_archived,
            timeout_seconds=timeout_seconds,
        )


class SymbolByIdServiceAdapter:
    def __init__(self, service: SymbolByIdUseCaseLike):
        self._service = service

    @property
    def in_progress(self) -> bool:
        return self._service.in_progress

    def set_callbacks(self, on_symbols_received=None, on_error=None, on_log=None) -> None:
        def handle_symbols(raw_symbols) -> None:
            if on_symbols_received:
                on_symbols_received(raw_symbols)

        self._service.set_callbacks(
            on_symbols_received=handle_symbols,
            on_error=on_error,
            on_log=on_log,
        )

    def clear_log_history(self) -> None:
        self._service.clear_log_history()

    def fetch(
        self,
        account_id: int,
        symbol_ids: list[int],
        include_archived: bool = False,
        timeout_seconds: Optional[int] = None,
    ) -> None:
        self._service.fetch(
            account_id=account_id,
            symbol_ids=symbol_ids,
            include_archived=include_archived,
            timeout_seconds=timeout_seconds,
        )


class CtidProfileServiceAdapter:
    def __init__(self, service: CtidProfileUseCaseLike):
        self._service = service

    @property
    def in_progress(self) -> bool:
        return self._service.in_progress

    def set_access_token(self, access_token: str) -> None:
        self._service.set_access_token(access_token)

    def set_callbacks(self, on_profile_received=None, on_error=None, on_log=None) -> None:
        def handle_profile(raw_profile) -> None:
            domain_profile = to_profile(raw_profile)
            if on_profile_received:
                on_profile_received(domain_profile)

        self._service.set_callbacks(
            on_profile_received=handle_profile,
            on_error=on_error,
            on_log=on_log,
        )

    def clear_log_history(self) -> None:
        self._service.clear_log_history()

    def fetch(self, timeout_seconds: Optional[int] = None) -> None:
        self._service.fetch(timeout_seconds)
