from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from forex.application.broker.protocols import BrokerUseCaseFactory
from forex.config.paths import TOKEN_FILE


class BrokerProvider(BrokerUseCaseFactory, ABC):
    """Abstract factory for broker services."""

    name: str

    @abstractmethod
    def create_app_auth(self, host_type: str, token_file: str = TOKEN_FILE):
        ...

    @abstractmethod
    def create_oauth(self, app_auth_service, token_file: str = TOKEN_FILE):
        ...

    @abstractmethod
    def create_oauth_login(self, token_file: str = TOKEN_FILE, redirect_uri: Optional[str] = None):
        ...

    @abstractmethod
    def create_account_list_service(self, app_auth_service, access_token: str):
        ...

    @abstractmethod
    def create_account_funds_service(self, app_auth_service):
        ...

    @abstractmethod
    def create_symbol_list_service(self, app_auth_service):
        ...

    @abstractmethod
    def create_symbol_by_id_service(self, app_auth_service):
        ...

    @abstractmethod
    def create_trendbar_service(self, app_auth_service):
        ...

    @abstractmethod
    def create_trendbar_history_service(self, app_auth_service):
        ...

    @abstractmethod
    def create_order_service(self, app_auth_service):
        ...


DEFAULT_PROVIDER = "ctrader"
_registry: dict[str, BrokerProvider] = {}


def register_provider(provider: BrokerProvider) -> None:
    _registry[provider.name] = provider


def get_provider(name: str = DEFAULT_PROVIDER) -> BrokerProvider:
    try:
        return _registry[name]
    except KeyError as exc:
        raise ValueError(f"Provider '{name}' is not registered") from exc


def available_providers() -> List[str]:
    return sorted(_registry.keys())
