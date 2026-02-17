# ui/train/widgets/trade_panel.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QGridLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from forex.domain.accounts import Account, AccountFundsSnapshot


class TradePanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._field_labels: dict[str, QLabel] = {}
        self._cards: list[QWidget] = []
        self._grid_layout: Optional[QGridLayout] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.setStyleSheet(
            """
            QScrollArea {
                background: transparent;
                border: none;
            }
            QWidget#tradeContent {
                background: transparent;
            }
            QFrame#infoCard {
                background: #1f242b;
                border: 1px solid #2c3138;
                border-radius: 10px;
            }
            QFrame#infoCardHeader {
                background: #232a33;
                border-bottom: 1px solid #2f353d;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                min-height: 34px;
            }
            QLabel#infoCardTitle {
                color: #cfd6df;
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#infoCardLabel {
                color: #9aa4b0;
                font-size: 11px;
            }
            QLabel#infoCardValue {
                color: #e6edf5;
                font-weight: 600;
            }
            """
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        content = QWidget()
        content.setObjectName("tradeContent")
        grid = QGridLayout(content)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        self._grid_layout = grid

        self._build_sections()
        self._layout_cards()

        scroll.setWidget(content)

        layout.addWidget(scroll)

    def _build_sections(self) -> None:
        self._add_section(
            "Account Basics",
            [
                ("account_id", "Account ID"),
                ("environment", "Environment"),
                ("account_trader_login", "Account Trader Login"),
                ("trader_account_id", "CTID Trader Account ID"),
                ("trader_login", "Trader Login"),
                ("broker_name", "Broker Name"),
                ("registration_timestamp", "Registration Time"),
                ("last_balance_update_timestamp", "Last Balance Update"),
                ("last_closing_deal_timestamp", "Last Close Time"),
            ],
        )
        self._add_section(
            "Funds/Currency",
            [
                ("balance", "Balance"),
                ("balance_version", "Balance Version"),
                ("equity", "Equity"),
                ("free_margin", "Free Margin"),
                ("used_margin", "Used Margin"),
                ("margin_level", "Margin Level"),
                ("currency", "Account Currency"),
                ("deposit_asset_id", "Deposit Asset ID"),
                ("money_digits", "Money Digits"),
            ],
        )
        self._add_section(
            "Bonuses",
            [
                ("manager_bonus", "Manager Bonus"),
                ("ib_bonus", "IB Bonus"),
                ("non_withdrawable_bonus", "Non-withdrawable Bonus"),
            ],
        )
        self._add_section(
            "Permissions/Type",
            [
                ("permission_scope", "Permission Scope"),
                ("access_rights", "Access Rights"),
                ("account_type", "Account Type"),
                ("swap_free", "Swap Free"),
                ("french_risk", "AMF Compliance"),
                ("is_limited_risk", "Limited Risk Account"),
            ],
        )
        self._add_section(
            "Commission Settings",
            [
                ("commission_symbol", "Symbol"),
                ("commission_value", "Commission"),
                ("commission_type", "Commission Type"),
                ("min_commission", "Min Commission"),
                ("min_commission_type", "Min Commission Type"),
                ("min_commission_asset", "Min Commission Asset"),
                ("rollover_commission", "Rollover Commission"),
                ("rollover_commission_3days", "3-day Rollover Day"),
                ("precise_trading_commission_rate", "Precise Commission Rate"),
                ("precise_min_commission", "Precise Min Commission"),
                ("pnl_conversion_fee_rate", "PnL Conversion Fee Rate"),
            ],
        )
        self._add_section(
            "Swap Settings",
            [
                ("swap_long", "Long Swap"),
                ("swap_short", "Short Swap"),
                ("swap_calculation_type", "Calculation Type"),
                ("swap_period", "Swap Period"),
                ("swap_time", "Swap Time"),
                ("charge_swap_at_weekends", "Charge at Weekends"),
                ("skip_swap_periods", "Skip Swap Periods"),
                ("swap_rollover_3days", "3-day Swap Rollover"),
            ],
        )
        self._add_section(
            "Leverage/Margin Strategy",
            [
                ("leverage_in_cents", "Leverage"),
                ("max_leverage", "Max Leverage"),
                ("total_margin_calculation_type", "Margin Calculation Type"),
                ("limited_risk_margin_calculation_strategy", "Limited-risk Margin Strategy"),
                ("stop_out_strategy", "Stop Out Strategy"),
                ("fair_stop_out", "Full/Partial Closeout"),
            ],
        )
        self._add_section(
            "Identity/Authorization",
            [
                ("ctid_user_id", "CTID User ID"),
                ("token_expires_at", "Token Expiry Time"),
                ("token_seconds_to_expiry", "Token Seconds Remaining"),
            ],
        )

    def _add_section(self, title: str, fields: list[tuple[str, str]]) -> None:
        card = QFrame()
        card.setObjectName("infoCard")
        card.setFrameShape(QFrame.StyledPanel)
        card.setFrameShadow(QFrame.Raised)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("infoCardHeader")
        header.setFixedHeight(36)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 12, 6)
        header_layout.setSpacing(0)
        title_label = QLabel(title)
        title_label.setObjectName("infoCardTitle")
        title_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        header_layout.addWidget(title_label)

        form = QFormLayout()
        form.setContentsMargins(12, 10, 12, 12)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(8)
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignTop)
        for key, label in fields:
            label_widget = QLabel(label)
            label_widget.setObjectName("infoCardLabel")
            value_widget = QLabel("-")
            value_widget.setObjectName("infoCardValue")
            value_widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
            form.addRow(label_widget, value_widget)
            self._field_labels[key] = value_widget
        card_layout.addWidget(header)
        card_layout.addLayout(form)
        self._cards.append(card)

    def _layout_cards(self) -> None:
        if not self._grid_layout:
            return
        grid = self._grid_layout
        while grid.count():
            item = grid.takeAt(0)
            if item and item.widget():
                item.widget().setParent(None)

        available = max(1, self.width() - 48)
        min_card_width = 320
        columns = max(1, min(4, available // min_card_width))
        row = 0
        col = 0
        for card in self._cards:
            grid.addWidget(card, row, col)
            col += 1
            if col >= columns:
                col = 0
                row += 1
        grid.setColumnStretch(columns, 1)

    def update_account_info(self, account: Account) -> None:
        env_text = "Live" if account.is_live else "Demo" if account.is_live is not None else "-"
        self._set_field("account_id", str(account.account_id))
        self._set_field("environment", env_text)
        self._set_field(
            "account_trader_login",
            "-" if account.trader_login is None else str(account.trader_login),
        )
        self._set_field(
            "permission_scope",
            self._format_enum(account.permission_scope, _PERMISSION_SCOPES),
        )
        self._set_field(
            "last_balance_update_timestamp",
            self._format_timestamp_ms(account.last_balance_update_timestamp),
        )
        self._set_field(
            "last_closing_deal_timestamp",
            self._format_timestamp_ms(account.last_closing_deal_timestamp),
        )

    def update_trader_info(self, snapshot: AccountFundsSnapshot) -> None:
        money_digits = snapshot.money_digits if snapshot.money_digits is not None else 2
        self._set_field("balance", self._format_money(snapshot.balance, money_digits))
        self._set_field("balance_version", self._format_int(snapshot.balance_version))
        self._set_field("equity", self._format_money(snapshot.equity, money_digits))
        self._set_field("free_margin", self._format_money(snapshot.free_margin, money_digits))
        self._set_field("used_margin", self._format_money(snapshot.used_margin, money_digits))
        self._set_field("margin_level", self._format_percent(snapshot.margin_level))
        self._set_field("currency", snapshot.currency or "-")
        self._set_field("money_digits", self._format_int(snapshot.money_digits))
        self._set_field("deposit_asset_id", self._format_int(snapshot.deposit_asset_id))
        self._set_field("trader_account_id", self._format_int(snapshot.ctid_trader_account_id))
        self._set_field("trader_login", self._format_int(snapshot.trader_login))
        self._set_field("broker_name", snapshot.broker_name or "-")
        self._set_field(
            "registration_timestamp",
            self._format_timestamp_ms(snapshot.registration_timestamp),
        )
        self._set_field("manager_bonus", self._format_money(snapshot.manager_bonus, money_digits))
        self._set_field("ib_bonus", self._format_money(snapshot.ib_bonus, money_digits))
        self._set_field(
            "non_withdrawable_bonus",
            self._format_money(snapshot.non_withdrawable_bonus, money_digits),
        )
        self._set_field(
            "access_rights",
            self._format_enum(snapshot.access_rights, _ACCESS_RIGHTS),
        )
        self._set_field(
            "account_type",
            self._format_enum(snapshot.account_type, _ACCOUNT_TYPES),
        )
        self._set_field("swap_free", self._format_bool(snapshot.swap_free))
        self._set_field("french_risk", self._format_bool(snapshot.french_risk))
        self._set_field("is_limited_risk", self._format_bool(snapshot.is_limited_risk))
        self._set_field(
            "leverage_in_cents",
            self._format_leverage(snapshot.leverage_in_cents),
        )
        self._set_field("max_leverage", self._format_leverage(snapshot.max_leverage))
        self._set_field(
            "total_margin_calculation_type",
            self._format_enum(snapshot.total_margin_calculation_type, _TOTAL_MARGIN_TYPES),
        )
        self._set_field(
            "limited_risk_margin_calculation_strategy",
            self._format_enum(
                snapshot.limited_risk_margin_calculation_strategy,
                _LIMITED_RISK_MARGIN_STRATEGIES,
            ),
        )
        self._set_field(
            "stop_out_strategy",
            self._format_enum(snapshot.stop_out_strategy, _STOP_OUT_STRATEGIES),
        )
        self._set_field("fair_stop_out", self._format_bool(snapshot.fair_stop_out))

    def update_profile_info(self, user_id: Optional[int]) -> None:
        self._set_field("ctid_user_id", self._format_int(user_id))

    def update_token_info(self, expires_at: Optional[int], seconds_to_expiry: Optional[int]) -> None:
        self._set_field("token_expires_at", self._format_timestamp_s(expires_at))
        self._set_field("token_seconds_to_expiry", self._format_int(seconds_to_expiry))

    def update_symbol_commission_info(self, symbol: dict) -> None:
        self._set_field(
            "commission_symbol",
            str(symbol.get("symbol_name") or symbol.get("symbol_id") or "-"),
        )
        self._set_field("commission_value", self._format_int(symbol.get("commission")))
        self._set_field(
            "commission_type",
            self._format_enum(symbol.get("commission_type"), _COMMISSION_TYPES),
        )
        self._set_field("min_commission", self._format_int(symbol.get("min_commission")))
        self._set_field(
            "min_commission_type",
            self._format_enum(symbol.get("min_commission_type"), _MIN_COMMISSION_TYPES),
        )
        self._set_field("min_commission_asset", str(symbol.get("min_commission_asset") or "-"))
        self._set_field("rollover_commission", self._format_int(symbol.get("rollover_commission")))
        self._set_field(
            "rollover_commission_3days",
            self._format_enum(symbol.get("rollover_commission_3days"), _DAYS_OF_WEEK),
        )
        self._set_field(
            "precise_trading_commission_rate",
            self._format_int(symbol.get("precise_trading_commission_rate")),
        )
        self._set_field(
            "precise_min_commission",
            self._format_int(symbol.get("precise_min_commission")),
        )
        self._set_field(
            "pnl_conversion_fee_rate",
            self._format_int(symbol.get("pnl_conversion_fee_rate")),
        )
        self._set_field("swap_long", self._format_int(symbol.get("swap_long")))
        self._set_field("swap_short", self._format_int(symbol.get("swap_short")))
        self._set_field(
            "swap_calculation_type",
            self._format_enum(symbol.get("swap_calculation_type"), _SWAP_CALC_TYPES),
        )
        self._set_field("swap_period", self._format_int(symbol.get("swap_period")))
        self._set_field("swap_time", self._format_int(symbol.get("swap_time")))
        self._set_field(
            "charge_swap_at_weekends",
            self._format_bool(symbol.get("charge_swap_at_weekends")),
        )
        self._set_field("skip_swap_periods", self._format_int(symbol.get("skip_swap_periods")))
        self._set_field(
            "swap_rollover_3days",
            self._format_enum(symbol.get("swap_rollover_3days"), _DAYS_OF_WEEK),
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_cards()

    def _set_field(self, key: str, value: str) -> None:
        label = self._field_labels.get(key)
        if label is not None:
            label.setText(value)

    @staticmethod
    def _format_int(value: Optional[int]) -> str:
        if value is None:
            return "-"
        return str(value)

    @staticmethod
    def _format_money(value: Optional[float], digits: int) -> str:
        if value is None:
            return "-"
        if digits <= 0:
            return str(int(round(value)))
        return f"{value:.{digits}f}"

    @staticmethod
    def _format_percent(value: Optional[float]) -> str:
        if value is None:
            return "-"
        return f"{value:.2f}%"

    @staticmethod
    def _format_bool(value: Optional[bool]) -> str:
        if value is None:
            return "-"
        return "Yes" if value else "No"

    @staticmethod
    def _format_enum(value: Optional[int], mapping: dict[int, str]) -> str:
        if value is None:
            return "-"
        name = mapping.get(int(value))
        if name is None:
            return f"{value}"
        return f"{name} ({value})"

    @staticmethod
    def _format_leverage(value: Optional[int]) -> str:
        if value is None:
            return "-"
        if value <= 0:
            return str(value)
        ratio = value / 100.0
        if ratio.is_integer():
            ratio_text = f"{int(ratio)}"
        else:
            ratio_text = f"{ratio:.2f}"
        return f"1:{ratio_text} ({value})"

    @staticmethod
    def _format_timestamp_ms(value: Optional[int]) -> str:
        if value is None:
            return "-"
        if value <= 0:
            return str(value)
        dt = datetime.fromtimestamp(value / 1000.0, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")

    @staticmethod
    def _format_timestamp_s(value: Optional[int]) -> str:
        if value is None:
            return "-"
        if value <= 0:
            return str(value)
        dt = datetime.fromtimestamp(value, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


_ACCESS_RIGHTS = {
    0: "FULL_ACCESS",
    1: "CLOSE_ONLY",
    2: "NO_TRADING",
    3: "NO_LOGIN",
}

_ACCOUNT_TYPES = {
    0: "HEDGED",
    1: "NETTED",
    2: "SPREAD_BETTING",
}

_TOTAL_MARGIN_TYPES = {
    0: "MAX",
    1: "SUM",
    2: "NET",
}

_LIMITED_RISK_MARGIN_STRATEGIES = {
    0: "ACCORDING_TO_LEVERAGE",
    1: "ACCORDING_TO_GSL",
    2: "ACCORDING_TO_GSL_AND_LEVERAGE",
}

_STOP_OUT_STRATEGIES = {
    0: "MOST_MARGIN_USED_FIRST",
    1: "MOST_LOSING_FIRST",
}

_PERMISSION_SCOPES = {
    0: "SCOPE_VIEW",
    1: "SCOPE_TRADE",
}

_COMMISSION_TYPES = {
    1: "USD_PER_MILLION_USD",
    2: "USD_PER_LOT",
    3: "PERCENTAGE_OF_VALUE",
    4: "QUOTE_CCY_PER_LOT",
}

_MIN_COMMISSION_TYPES = {
    1: "CURRENCY",
    2: "QUOTE_CURRENCY",
}

_DAYS_OF_WEEK = {
    0: "NONE",
    1: "MONDAY",
    2: "TUESDAY",
    3: "WEDNESDAY",
    4: "THURSDAY",
    5: "FRIDAY",
    6: "SATURDAY",
    7: "SUNDAY",
}

_SWAP_CALC_TYPES = {
    0: "PIPS",
    1: "PERCENTAGE",
    2: "POINTS",
    3: "ABSOLUTE",
}
