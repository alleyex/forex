from dataclasses import dataclass
from typing import Optional


@dataclass
class Account:
    """Simplified account descriptor."""
    account_id: int
    is_live: Optional[bool]
    trader_login: Optional[int]
    permission_scope: Optional[int] = None
    last_closing_deal_timestamp: Optional[int] = None
    last_balance_update_timestamp: Optional[int] = None


@dataclass
class AccountFundsSnapshot:
    balance: Optional[float]
    balance_version: Optional[int]
    equity: Optional[float]
    free_margin: Optional[float]
    used_margin: Optional[float]
    margin_level: Optional[float]
    currency: Optional[str]
    money_digits: Optional[int]
    ctid_trader_account_id: Optional[int]
    manager_bonus: Optional[float]
    ib_bonus: Optional[float]
    non_withdrawable_bonus: Optional[float]
    access_rights: Optional[int]
    deposit_asset_id: Optional[int]
    swap_free: Optional[bool]
    leverage_in_cents: Optional[int]
    total_margin_calculation_type: Optional[int]
    max_leverage: Optional[int]
    french_risk: Optional[bool]
    trader_login: Optional[int]
    account_type: Optional[int]
    broker_name: Optional[str]
    registration_timestamp: Optional[int]
    is_limited_risk: Optional[bool]
    limited_risk_margin_calculation_strategy: Optional[int]
    fair_stop_out: Optional[bool]
    stop_out_strategy: Optional[int]


@dataclass
class AccountProfile:
    user_id: Optional[int]
