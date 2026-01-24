from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, Optional, TypeVar

from application.broker.adapters import (
    AccountFundsServiceAdapter,
    AccountListServiceAdapter,
    SymbolListServiceAdapter,
)
from application.broker.protocols import (
    AccountFundsUseCaseLike,
    AccountListUseCaseLike,
    AppAuthServiceLike,
    BrokerUseCaseFactory,
    OAuthLoginServiceLike,
    OAuthServiceLike,
    SymbolListUseCaseLike,
    TrendbarHistoryServiceLike,
    TrendbarServiceLike,
)
from config.paths import TOKEN_FILE


TUseCase = TypeVar("TUseCase")


@dataclass
class _UseCaseCache(Generic[TUseCase]):
    use_case: Optional[TUseCase] = None
    owner: Optional[AppAuthServiceLike] = None

    def get(
        self,
        owner: AppAuthServiceLike,
        create: Callable[[], TUseCase],
        update: Optional[Callable[[TUseCase], None]] = None,
    ) -> TUseCase:
        if self.use_case is None or self.owner is not owner:
            self.use_case = create()
            self.owner = owner
        elif update:
            update(self.use_case)
        return self.use_case


class BrokerUseCases:
    """
    Facade over broker provider for application/UI layer.

    Keeps creation logic centralized so UI depends on this abstraction
    instead of concrete provider implementations.
    """

    def __init__(self, provider: BrokerUseCaseFactory):
        self._provider = provider
        self._account_list_cache: _UseCaseCache[AccountListUseCase] = _UseCaseCache()
        self._account_funds_cache: _UseCaseCache[AccountFundsUseCase] = _UseCaseCache()
        self._symbol_list_cache: _UseCaseCache[SymbolListUseCase] = _UseCaseCache()

    def create_app_auth(self, host_type: str, token_file: str = TOKEN_FILE) -> AppAuthServiceLike:
        return self._provider.create_app_auth(host_type, token_file)

    def create_oauth(
        self, app_auth_service: AppAuthServiceLike, token_file: str = TOKEN_FILE
    ) -> OAuthServiceLike:
        return self._provider.create_oauth(app_auth_service, token_file)

    def create_oauth_login(
        self, token_file: str = TOKEN_FILE, redirect_uri: Optional[str] = None
    ) -> OAuthLoginServiceLike:
        return self._provider.create_oauth_login(token_file=token_file, redirect_uri=redirect_uri)

    def create_account_list(
        self, app_auth_service: AppAuthServiceLike, access_token: str
    ) -> AccountListUseCaseLike:
        service = self._provider.create_account_list_service(
            app_auth_service=app_auth_service, access_token=access_token
        )
        return AccountListUseCase(AccountListServiceAdapter(service))

    def create_account_funds(self, app_auth_service: AppAuthServiceLike) -> AccountFundsUseCaseLike:
        service = self._provider.create_account_funds_service(app_auth_service=app_auth_service)
        return AccountFundsUseCase(AccountFundsServiceAdapter(service))

    def create_symbol_list(self, app_auth_service: AppAuthServiceLike) -> SymbolListUseCaseLike:
        service = self._provider.create_symbol_list_service(app_auth_service=app_auth_service)
        return SymbolListUseCase(SymbolListServiceAdapter(service))

    def create_trendbar(self, app_auth_service: AppAuthServiceLike) -> TrendbarServiceLike:
        return self._provider.create_trendbar_service(app_auth_service=app_auth_service)

    def create_trendbar_history(self, app_auth_service: AppAuthServiceLike) -> TrendbarHistoryServiceLike:
        return self._provider.create_trendbar_history_service(app_auth_service=app_auth_service)

    def account_list_in_progress(self) -> bool:
        return bool(self._account_list_cache.use_case and self._account_list_cache.use_case.in_progress)

    def account_funds_in_progress(self) -> bool:
        return bool(self._account_funds_cache.use_case and self._account_funds_cache.use_case.in_progress)

    def symbol_list_in_progress(self) -> bool:
        return bool(self._symbol_list_cache.use_case and self._symbol_list_cache.use_case.in_progress)

    def fetch_accounts(
        self,
        app_auth_service: AppAuthServiceLike,
        access_token: str,
        on_accounts_received=None,
        on_error=None,
        on_log=None,
        timeout_seconds: Optional[int] = None,
    ) -> bool:
        account_list_uc = self._account_list_cache.get(
            app_auth_service,
            lambda: self.create_account_list(app_auth_service, access_token),
            update=lambda uc: uc.set_access_token(access_token),
        )

        if account_list_uc.in_progress:
            return False

        account_list_uc.clear_log_history()
        account_list_uc.set_callbacks(
            on_accounts_received=on_accounts_received,
            on_error=on_error,
            on_log=on_log,
        )
        account_list_uc.fetch(timeout_seconds)
        return True

    def fetch_account_funds(
        self,
        app_auth_service: AppAuthServiceLike,
        account_id: int,
        on_funds_received=None,
        on_error=None,
        on_log=None,
        timeout_seconds: Optional[int] = None,
    ) -> bool:
        account_funds_uc = self._account_funds_cache.get(
            app_auth_service,
            lambda: self.create_account_funds(app_auth_service),
        )

        if account_funds_uc.in_progress:
            return False

        account_funds_uc.clear_log_history()
        account_funds_uc.set_callbacks(
            on_funds_received=on_funds_received,
            on_error=on_error,
            on_log=on_log,
        )
        account_funds_uc.fetch(account_id, timeout_seconds)
        return True

    def fetch_symbols(
        self,
        app_auth_service: AppAuthServiceLike,
        account_id: int,
        include_archived: bool = False,
        on_symbols_received=None,
        on_error=None,
        on_log=None,
        timeout_seconds: Optional[int] = None,
    ) -> bool:
        symbol_list_uc = self._symbol_list_cache.get(
            app_auth_service,
            lambda: self.create_symbol_list(app_auth_service),
        )

        if symbol_list_uc.in_progress:
            return False

        symbol_list_uc.clear_log_history()
        symbol_list_uc.set_callbacks(
            on_symbols_received=on_symbols_received,
            on_error=on_error,
            on_log=on_log,
        )
        symbol_list_uc.fetch(
            account_id=account_id,
            include_archived=include_archived,
            timeout_seconds=timeout_seconds,
        )
        return True


class AccountListUseCase:
    def __init__(self, adapter: AccountListServiceAdapter):
        self._adapter = adapter

    @property
    def in_progress(self) -> bool:
        return self._adapter.in_progress

    def set_access_token(self, access_token: str) -> None:
        self._adapter.set_access_token(access_token)

    def set_callbacks(self, on_accounts_received=None, on_error=None, on_log=None) -> None:
        self._adapter.set_callbacks(
            on_accounts_received=on_accounts_received,
            on_error=on_error,
            on_log=on_log,
        )

    def clear_log_history(self) -> None:
        self._adapter.clear_log_history()

    def fetch(self, timeout_seconds: Optional[int] = None) -> None:
        self._adapter.fetch(timeout_seconds)


class AccountFundsUseCase:
    def __init__(self, adapter: AccountFundsServiceAdapter):
        self._adapter = adapter

    @property
    def in_progress(self) -> bool:
        return self._adapter.in_progress

    def set_callbacks(self, on_funds_received=None, on_error=None, on_log=None) -> None:
        self._adapter.set_callbacks(
            on_funds_received=on_funds_received,
            on_error=on_error,
            on_log=on_log,
        )

    def clear_log_history(self) -> None:
        self._adapter.clear_log_history()

    def fetch(self, account_id: int, timeout_seconds: Optional[int] = None) -> None:
        self._adapter.fetch(account_id, timeout_seconds)


class SymbolListUseCase:
    def __init__(self, adapter: SymbolListServiceAdapter):
        self._adapter = adapter

    @property
    def in_progress(self) -> bool:
        return self._adapter.in_progress

    def set_callbacks(self, on_symbols_received=None, on_error=None, on_log=None) -> None:
        self._adapter.set_callbacks(
            on_symbols_received=on_symbols_received,
            on_error=on_error,
            on_log=on_log,
        )

    def clear_log_history(self) -> None:
        self._adapter.clear_log_history()

    def fetch(
        self,
        account_id: int,
        include_archived: bool = False,
        timeout_seconds: Optional[int] = None,
    ) -> None:
        self._adapter.fetch(
            account_id=account_id,
            include_archived=include_archived,
            timeout_seconds=timeout_seconds,
        )
