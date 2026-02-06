from __future__ import annotations

from typing import Optional

from forex.application.broker.provider import BrokerProvider
from forex.infrastructure.broker.ctrader.services.account_funds_service import AccountFundsService
from forex.infrastructure.broker.ctrader.services.account_list_service import AccountListService
from forex.infrastructure.broker.ctrader.services.app_auth_service import AppAuthService
from forex.infrastructure.broker.ctrader.services.oauth_login_service import OAuthLoginService
from forex.infrastructure.broker.ctrader.services.oauth_service import OAuthService
from forex.infrastructure.broker.ctrader.services.symbol_by_id_service import SymbolByIdService
from forex.infrastructure.broker.ctrader.services.symbol_list_service import SymbolListService
from forex.infrastructure.broker.ctrader.services.trendbar_history_service import TrendbarHistoryService
from forex.infrastructure.broker.ctrader.services.trendbar_service import TrendbarService
from forex.infrastructure.broker.ctrader.services.order_service import OrderService
from forex.config.paths import TOKEN_FILE


class CTraderProvider(BrokerProvider):
    """cTrader adapter implementing BrokerProvider."""

    name = "ctrader"

    def create_app_auth(self, host_type: str, token_file: str = TOKEN_FILE) -> AppAuthService:
        return AppAuthService.create(host_type, token_file)

    def create_oauth(self, app_auth_service: AppAuthService, token_file: str = TOKEN_FILE) -> OAuthService:
        return OAuthService.create(app_auth_service, token_file)

    def create_oauth_login(
        self, token_file: str = TOKEN_FILE, redirect_uri: Optional[str] = None
    ) -> OAuthLoginService:
        redirect = redirect_uri or "http://127.0.0.1:8765/callback"
        return OAuthLoginService.create(token_file=token_file, redirect_uri=redirect)

    def create_account_list_service(
        self, app_auth_service: AppAuthService, access_token: str
    ) -> AccountListService:
        return AccountListService(app_auth_service=app_auth_service, access_token=access_token)

    def create_account_funds_service(self, app_auth_service: AppAuthService) -> AccountFundsService:
        return AccountFundsService(app_auth_service=app_auth_service)

    def create_symbol_list_service(self, app_auth_service: AppAuthService) -> SymbolListService:
        return SymbolListService(app_auth_service=app_auth_service)

    def create_symbol_by_id_service(self, app_auth_service: AppAuthService) -> SymbolByIdService:
        return SymbolByIdService(app_auth_service=app_auth_service)

    def create_trendbar_service(self, app_auth_service: AppAuthService) -> TrendbarService:
        return TrendbarService(app_auth_service=app_auth_service)

    def create_trendbar_history_service(self, app_auth_service: AppAuthService) -> TrendbarHistoryService:
        return TrendbarHistoryService(app_auth_service=app_auth_service)

    def create_order_service(self, app_auth_service: AppAuthService) -> OrderService:
        return OrderService(app_auth_service=app_auth_service)
