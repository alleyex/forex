from dataclasses import dataclass
from typing import Optional


@dataclass
class Account:
    """Simplified account descriptor."""
    account_id: int
    is_live: Optional[bool]
    trader_login: Optional[int]


@dataclass
class AccountFundsSnapshot:
    balance: Optional[float]
    equity: Optional[float]
    free_margin: Optional[float]
    used_margin: Optional[float]
    margin_level: Optional[float]
    currency: Optional[str]
    money_digits: Optional[int]
