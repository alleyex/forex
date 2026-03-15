from dataclasses import dataclass


@dataclass
class Account:
    """Simplified account descriptor."""

    account_id: int
    is_live: bool | None
    trader_login: int | None
    permission_scope: int | None = None
    last_closing_deal_timestamp: int | None = None
    last_balance_update_timestamp: int | None = None


@dataclass
class AccountFundsSnapshot:
    balance: float | None
    balance_version: int | None
    equity: float | None
    free_margin: float | None
    used_margin: float | None
    margin_level: float | None
    currency: str | None
    money_digits: int | None
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


@dataclass
class AccountProfile:
    user_id: int | None
