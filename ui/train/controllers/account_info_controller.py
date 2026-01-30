from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QObject

from application import AppAuthServiceLike, BrokerUseCases
from domain import AccountFundsSnapshot
from ui.shared.utils.formatters import format_connection_message
from utils.reactor_manager import reactor_manager


class AccountInfoController(QObject):
    def __init__(
        self,
        *,
        parent: QObject,
        log: Callable[[str], None],
        use_cases: Optional[BrokerUseCases] = None,
        service: Optional[AppAuthServiceLike] = None,
    ) -> None:
        super().__init__(parent)
        self._log = log
        self._use_cases = use_cases
        self._service = service

    def set_use_cases(self, use_cases: Optional[BrokerUseCases]) -> None:
        self._use_cases = use_cases

    def set_service(self, service: Optional[AppAuthServiceLike]) -> None:
        self._service = service

    def handle_accounts_received(self, accounts: list, account_id: Optional[int]) -> None:
        try:
            self._log(format_connection_message("account_count", count=len(accounts)))
            if not accounts:
                self._log(format_connection_message("account_list_empty"))
                return

            selected = None
            if account_id:
                for item in accounts:
                    if item.account_id == int(account_id):
                        selected = item
                        break
            if selected is None:
                selected = accounts[0]

            env_text = "真實" if selected.is_live else "模擬"
            login_text = "-" if selected.trader_login is None else str(selected.trader_login)
            self._log(format_connection_message("account_info_header"))
            self._log(
                format_connection_message("account_field", label="帳戶 ID", value=selected.account_id)
            )
            self._log(format_connection_message("account_field", label="環境", value=env_text))
            self._log(format_connection_message("account_field", label="交易登入", value=login_text))
            self._fetch_account_funds(selected.account_id)
        except Exception as exc:
            self._log(format_connection_message("account_parse_failed", error=exc))

    def handle_funds_received(self, funds: AccountFundsSnapshot) -> None:
        snapshot = funds
        self._log(format_connection_message("funds_header"))
        money_digits = snapshot.money_digits if snapshot.money_digits is not None else 2
        self._log(
            format_connection_message(
                "funds_field",
                label="餘額",
                value=self._format_money(snapshot.balance, money_digits),
            )
        )
        self._log(
            format_connection_message(
                "funds_field",
                label="淨值",
                value=self._format_money(snapshot.equity, money_digits),
            )
        )
        self._log(
            format_connection_message(
                "funds_field",
                label="可用資金",
                value=self._format_money(snapshot.free_margin, money_digits),
            )
        )
        self._log(
            format_connection_message(
                "funds_field",
                label="已用保證金",
                value=self._format_money(snapshot.used_margin, money_digits),
            )
        )
        if snapshot.margin_level is None:
            margin_text = "-"
        else:
            margin_text = f"{snapshot.margin_level:.2f}%"
        self._log(format_connection_message("funds_field", label="保證金比例", value=margin_text))
        self._log(
            format_connection_message(
                "funds_field",
                label="帳戶幣別",
                value=snapshot.currency or "-",
            )
        )

    def _fetch_account_funds(self, account_id: int) -> None:
        if not self._service:
            self._log(format_connection_message("missing_app_auth"))
            return

        if self._use_cases is None:
            self._log(format_connection_message("missing_use_cases"))
            return
        if self._use_cases.account_funds_in_progress():
            self._log(format_connection_message("fetching_funds"))
            return
        reactor_manager.ensure_running()
        from twisted.internet import reactor

        reactor.callFromThread(
            self._use_cases.fetch_account_funds,
            self._service,
            account_id,
            self.handle_funds_received,
            lambda e: self._log(format_connection_message("funds_error", error=e)),
            self._log,
        )

    @staticmethod
    def _format_money(value: Optional[float], digits: int) -> str:
        if value is None:
            return "-"
        if digits <= 0:
            return str(int(round(value)))
        return f"{value:.{digits}f}"
