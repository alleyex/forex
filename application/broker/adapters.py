from __future__ import annotations

from typing import Iterable, Optional, Protocol

from application.broker.protocols import (
    AccountFundsLike,
    AccountFundsUseCaseLike,
    AccountListUseCaseLike,
    SymbolByIdUseCaseLike,
    SymbolListUseCaseLike,
)
from domain import Account, AccountFundsSnapshot, Symbol


class AccountInfoLike(Protocol):
    account_id: int
    is_live: Optional[bool]
    trader_login: Optional[int]

class SymbolInfoLike(Protocol):
    symbol_id: int
    symbol_name: str


def to_account(info: AccountInfoLike) -> Account:
    return Account(
        account_id=int(info.account_id),
        is_live=info.is_live,
        trader_login=info.trader_login,
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
                )
            )
        except Exception:
            continue
    return accounts


def to_funds_snapshot(funds: AccountFundsLike) -> AccountFundsSnapshot:
    return AccountFundsSnapshot(
        balance=funds.balance,
        equity=funds.equity,
        free_margin=funds.free_margin,
        used_margin=funds.used_margin,
        margin_level=funds.margin_level,
        currency=funds.currency,
        money_digits=funds.money_digits,
    )


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
