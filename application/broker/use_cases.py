from __future__ import annotations

from typing import Optional

from application.broker.adapters import AccountFundsServiceAdapter, AccountListServiceAdapter
from application.broker.protocols import (
    AccountFundsUseCaseLike,
    AccountListUseCaseLike,
    AppAuthServiceLike,
    BrokerUseCaseFactory,
    OAuthLoginServiceLike,
    OAuthServiceLike,
    TrendbarHistoryServiceLike,
    TrendbarServiceLike,
)
from config.paths import TOKEN_FILE


class BrokerUseCases:
    """
    Facade over broker provider for application/UI layer.

    Keeps creation logic centralized so UI depends on this abstraction
    instead of concrete provider implementations.
    """

    def __init__(self, provider: BrokerUseCaseFactory):
        self._provider = provider
        self._account_list_uc: Optional[AccountListUseCase] = None
        self._account_funds_uc: Optional[AccountFundsUseCase] = None

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

    def create_trendbar(self, app_auth_service: AppAuthServiceLike) -> TrendbarServiceLike:
        return self._provider.create_trendbar_service(app_auth_service=app_auth_service)

    def create_trendbar_history(self, app_auth_service: AppAuthServiceLike) -> TrendbarHistoryServiceLike:
        return self._provider.create_trendbar_history_service(app_auth_service=app_auth_service)

    def account_list_in_progress(self) -> bool:
        return bool(self._account_list_uc and self._account_list_uc.in_progress)

    def account_funds_in_progress(self) -> bool:
        return bool(self._account_funds_uc and self._account_funds_uc.in_progress)

    def fetch_accounts(
        self,
        app_auth_service: AppAuthServiceLike,
        access_token: str,
        on_accounts_received=None,
        on_error=None,
        on_log=None,
        timeout_seconds: Optional[int] = None,
    ) -> bool:
        if self._account_list_uc is None:
            self._account_list_uc = self.create_account_list(app_auth_service, access_token)
        else:
            self._account_list_uc.set_access_token(access_token)

        if self._account_list_uc.in_progress:
            return False

        self._account_list_uc.clear_log_history()
        self._account_list_uc.set_callbacks(
            on_accounts_received=on_accounts_received,
            on_error=on_error,
            on_log=on_log,
        )
        self._account_list_uc.fetch(timeout_seconds)
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
        if self._account_funds_uc is None:
            self._account_funds_uc = self.create_account_funds(app_auth_service)

        if self._account_funds_uc.in_progress:
            return False

        self._account_funds_uc.clear_log_history()
        self._account_funds_uc.set_callbacks(
            on_funds_received=on_funds_received,
            on_error=on_error,
            on_log=on_log,
        )
        self._account_funds_uc.fetch(account_id, timeout_seconds)
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
