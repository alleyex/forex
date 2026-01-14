from dataclasses import dataclass
from typing import Iterable, List, Optional


@dataclass(frozen=True)
class AccountInfo:
    """Account information for selection and display."""

    account_id: int
    is_live: Optional[bool]
    trader_login: Optional[int] = None

    @classmethod
    def from_dict(cls, data: dict) -> "AccountInfo":
        return cls(
            account_id=int(data.get("account_id", 0)),
            is_live=bool(data.get("is_live", False)) if data.get("is_live") is not None else None,
            trader_login=data.get("trader_login"),
        )


def parse_accounts(raw_accounts: Iterable[dict]) -> List[AccountInfo]:
    """Normalize raw account payloads into AccountInfo objects."""
    accounts: List[AccountInfo] = []
    for item in raw_accounts:
        try:
            accounts.append(AccountInfo.from_dict(item))
        except Exception:
            continue
    return accounts
