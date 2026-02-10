"""
帳戶資金狀態服務
"""
from dataclasses import dataclass
import time
from typing import Callable, Optional, Protocol, Sequence

from ctrader_open_api import Client
from ctrader_open_api.messages.OpenApiMessages_pb2 import (
    ProtoOAAssetListReq,
    ProtoOAGetPositionUnrealizedPnLReq,
    ProtoOAReconcileReq,
    ProtoOATraderReq,
)
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOAPayloadType

from forex.infrastructure.broker.base import BaseCallbacks, LogHistoryMixin, OperationStateMixin, build_callbacks
from forex.infrastructure.broker.errors import ErrorCode, error_message
from forex.infrastructure.broker.ctrader.services.app_auth_service import AppAuthService
from forex.infrastructure.broker.ctrader.services.base import CTraderRequestLifecycleMixin
from forex.infrastructure.broker.ctrader.services.message_helpers import (
    format_error,
    is_already_subscribed,
    format_warning,
)
from forex.infrastructure.broker.ctrader.services.timeout_tracker import TimeoutTracker
from forex.utils.metrics import metrics


class TraderMessage(Protocol):
    payloadType: int
    trader: object


class ReconcileMessage(Protocol):
    payloadType: int
    position: Sequence[object]


class PositionMessage(Protocol):
    positionId: int
    usedMargin: int
    moneyDigits: int


class PnlMessage(Protocol):
    payloadType: int
    moneyDigits: int
    positionUnrealizedPnL: Sequence[object]


class PnlItem(Protocol):
    positionId: int
    netUnrealizedPnL: int


class AssetMessage(Protocol):
    payloadType: int
    asset: Sequence[object]


class AssetItem(Protocol):
    assetId: int
    name: str
    displayName: str


class ErrorMessage(Protocol):
    payloadType: int
    errorCode: int
    description: str


@dataclass(frozen=True)
class AccountFunds:
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
class AccountFundsServiceCallbacks(BaseCallbacks):
    """AccountFundsService 的回調函式"""
    on_funds_received: Optional[Callable[[AccountFunds], None]] = None
    on_position_pnl: Optional[Callable[[dict[int, float]], None]] = None


class AccountFundsService(
    CTraderRequestLifecycleMixin,
    LogHistoryMixin[AccountFundsServiceCallbacks],
    OperationStateMixin,
):
    """
    取得帳戶資金狀態（餘額、淨值、保證金）
    """

    def __init__(self, app_auth_service: AppAuthService):
        self._app_auth_service = app_auth_service
        self._callbacks = AccountFundsServiceCallbacks()
        self._in_progress = False
        self._timeout_tracker = TimeoutTracker(self._on_timeout)
        self._log_history = []
        self._last_pnl_request_ts: float = 0.0
        self._min_pnl_interval: float = 2.0
        self._reset_state()

    def set_callbacks(
        self,
        on_funds_received: Optional[Callable[[AccountFunds], None]] = None,
        on_position_pnl: Optional[Callable[[dict[int, float]], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> None:
        """設定回調函式"""
        self._callbacks = build_callbacks(
            AccountFundsServiceCallbacks,
            on_funds_received=on_funds_received,
            on_position_pnl=on_position_pnl,
            on_error=on_error,
            on_log=on_log,
        )
        self._replay_log_history()

    def fetch(self, account_id: int, timeout_seconds: Optional[int] = None) -> None:
        """取得帳戶資金狀態"""
        if not self._start_operation():
            self._log("⚠️ 帳戶資金查詢進行中")
            return

        self._reset_state()
        self._account_id = int(account_id)
        self._await_trader = True
        self._await_reconcile = True
        self._await_assets = True

        try:
            self._client = self._app_auth_service.get_client()
        except Exception as exc:
            self._emit_error(str(exc))
            self._end_operation()
            return

        self._begin_request_lifecycle(
            timeout_tracker=self._timeout_tracker,
            timeout_seconds=timeout_seconds,
            retry_request=self._retry_request,
            handler=self._handle_message,
            send_request=self._send_initial_requests,
        )

    def _send_initial_requests(self) -> None:
        self._send_trader_request()
        self._send_reconcile_request()
        self._send_asset_list_request()

    def _reset_state(self) -> None:
        self._client: Optional[Client] = None
        self._account_id: Optional[int] = None
        self._await_trader = False
        self._await_reconcile = False
        self._await_pnl = False
        self._await_assets = False
        self._balance: Optional[float] = None
        self._balance_version: Optional[int] = None
        self._deposit_asset_id: Optional[int] = None
        self._money_digits: Optional[int] = None
        self._ctid_trader_account_id: Optional[int] = None
        self._manager_bonus: Optional[float] = None
        self._ib_bonus: Optional[float] = None
        self._non_withdrawable_bonus: Optional[float] = None
        self._access_rights: Optional[int] = None
        self._swap_free: Optional[bool] = None
        self._leverage_in_cents: Optional[int] = None
        self._total_margin_calculation_type: Optional[int] = None
        self._max_leverage: Optional[int] = None
        self._french_risk: Optional[bool] = None
        self._trader_login: Optional[int] = None
        self._account_type: Optional[int] = None
        self._broker_name: Optional[str] = None
        self._registration_timestamp: Optional[int] = None
        self._is_limited_risk: Optional[bool] = None
        self._limited_risk_margin_calculation_strategy: Optional[int] = None
        self._fair_stop_out: Optional[bool] = None
        self._stop_out_strategy: Optional[int] = None
        self._used_margin: float = 0.0
        self._net_unrealized_pnl: float = 0.0
        self._assets_by_id: dict[int, str] = {}

    def _send_trader_request(self) -> None:
        request = ProtoOATraderReq()
        request.ctidTraderAccountId = self._account_id
        self._client.send(request)

    def _send_reconcile_request(self) -> None:
        request = ProtoOAReconcileReq()
        request.ctidTraderAccountId = self._account_id
        self._client.send(request)

    def _send_asset_list_request(self) -> None:
        request = ProtoOAAssetListReq()
        request.ctidTraderAccountId = self._account_id
        self._client.send(request)

    def _send_pnl_request(self, position_ids: Sequence[int]) -> None:
        now = time.monotonic()
        if now - self._last_pnl_request_ts < self._min_pnl_interval:
            return
        self._last_pnl_request_ts = now
        request = ProtoOAGetPositionUnrealizedPnLReq()
        request.ctidTraderAccountId = self._account_id
        self._await_pnl = True
        self._client.send(request)

    def _handle_message(self, client: Client, msg: object) -> bool:
        """處理帳戶資金相關回應"""
        if not self._in_progress:
            return False

        payload = getattr(msg, "payloadType", None)
        if payload == ProtoOAPayloadType.PROTO_OA_TRADER_RES:
            self._on_trader(msg)
            return True

        if payload == ProtoOAPayloadType.PROTO_OA_RECONCILE_RES:
            self._on_reconcile(msg)
            return True

        if payload == ProtoOAPayloadType.PROTO_OA_GET_POSITION_UNREALIZED_PNL_RES:
            self._on_pnl(msg)
            return True

        if payload == ProtoOAPayloadType.PROTO_OA_ASSET_LIST_RES:
            self._on_assets(msg)
            return True

        if payload == ProtoOAPayloadType.PROTO_OA_ERROR_RES:
            if is_already_subscribed(getattr(msg, "errorCode", ""), getattr(msg, "description", "")):
                return True
            self._log(format_error(getattr(msg, "errorCode", ""), getattr(msg, "description", "")))
            self._on_error(msg)
            return True

        return False

    def _on_trader(self, msg: TraderMessage) -> None:
        trader = getattr(msg, "trader", None)
        if trader is not None:
            self._ctid_trader_account_id = int(getattr(trader, "ctidTraderAccountId", 0))
            self._money_digits = int(getattr(trader, "moneyDigits", 0))
            self._deposit_asset_id = int(getattr(trader, "depositAssetId", 0))
            raw_balance = int(getattr(trader, "balance", 0))
            self._balance = self._scale_money(raw_balance, self._money_digits)
            self._balance_version = int(getattr(trader, "balanceVersion", 0))
            self._manager_bonus = self._scale_money(
                int(getattr(trader, "managerBonus", 0)), self._money_digits
            )
            self._ib_bonus = self._scale_money(
                int(getattr(trader, "ibBonus", 0)), self._money_digits
            )
            self._non_withdrawable_bonus = self._scale_money(
                int(getattr(trader, "nonWithdrawableBonus", 0)), self._money_digits
            )
            self._access_rights = int(getattr(trader, "accessRights", 0))
            self._swap_free = bool(getattr(trader, "swapFree", False))
            self._leverage_in_cents = int(getattr(trader, "leverageInCents", 0))
            self._total_margin_calculation_type = int(
                getattr(trader, "totalMarginCalculationType", 0)
            )
            self._max_leverage = int(getattr(trader, "maxLeverage", 0))
            self._french_risk = bool(getattr(trader, "frenchRisk", False))
            self._trader_login = int(getattr(trader, "traderLogin", 0))
            self._account_type = int(getattr(trader, "accountType", 0))
            self._broker_name = str(getattr(trader, "brokerName", "") or "")
            self._registration_timestamp = int(getattr(trader, "registrationTimestamp", 0))
            self._is_limited_risk = bool(getattr(trader, "isLimitedRisk", False))
            self._limited_risk_margin_calculation_strategy = int(
                getattr(trader, "limitedRiskMarginCalculationStrategy", 0)
            )
            self._fair_stop_out = bool(getattr(trader, "fairStopOut", False))
            self._stop_out_strategy = int(getattr(trader, "stopOutStrategy", 0))
        self._await_trader = False
        self._maybe_finish()

    def _on_reconcile(self, msg: ReconcileMessage) -> None:
        positions = list(getattr(msg, "position", []))
        self._used_margin = 0.0
        position_ids = []
        for position in positions:
            money_digits = int(getattr(position, "moneyDigits", self._money_digits or 0))
            used_margin = int(getattr(position, "usedMargin", 0))
            self._used_margin += self._scale_money(used_margin, money_digits)
            position_ids.append(int(getattr(position, "positionId", 0)))
        self._await_reconcile = False
        if position_ids:
            self._send_pnl_request(position_ids)
        else:
            self._await_pnl = False
            self._net_unrealized_pnl = 0.0
        self._maybe_finish()

    def _on_pnl(self, msg: PnlMessage) -> None:
        money_digits = int(getattr(msg, "moneyDigits", self._money_digits or 0))
        pnl_items = list(getattr(msg, "positionUnrealizedPnL", []))
        net_pnl = 0.0
        position_pnl: dict[int, float] = {}
        for item in pnl_items:
            net_value = int(getattr(item, "netUnrealizedPnL", 0))
            position_id = int(getattr(item, "positionId", 0))
            if position_id:
                position_pnl[position_id] = self._scale_money(net_value, money_digits)
            net_pnl += self._scale_money(net_value, money_digits)
        self._net_unrealized_pnl = net_pnl
        self._await_pnl = False
        if self._callbacks.on_position_pnl:
            self._callbacks.on_position_pnl(position_pnl)
        self._maybe_finish()

    def _on_assets(self, msg: AssetMessage) -> None:
        assets = list(getattr(msg, "asset", []))
        self._assets_by_id = {
            int(getattr(asset, "assetId", 0)): getattr(asset, "displayName", None)
            or getattr(asset, "name", "")
            for asset in assets
        }
        self._await_assets = False
        self._maybe_finish()

    def _on_error(self, msg: ErrorMessage) -> None:
        self._emit_error(format_error(msg.errorCode, msg.description))
        metrics.inc("ctrader.account_funds.error")
        self._cleanup()

    def _maybe_finish(self) -> None:
        if self._await_trader or self._await_reconcile or self._await_pnl or self._await_assets:
            return

        balance = self._balance
        equity = None if balance is None else balance + self._net_unrealized_pnl
        used_margin = self._used_margin
        free_margin = None if equity is None else equity - used_margin
        margin_level = None
        if used_margin > 0 and equity is not None:
            margin_level = (equity / used_margin) * 100

        currency = None
        if self._deposit_asset_id:
            currency = self._assets_by_id.get(self._deposit_asset_id, str(self._deposit_asset_id))

        funds = AccountFunds(
            balance=balance,
            balance_version=self._balance_version,
            equity=equity,
            free_margin=free_margin,
            used_margin=used_margin,
            margin_level=margin_level,
            currency=currency,
            money_digits=self._money_digits,
            ctid_trader_account_id=self._ctid_trader_account_id,
            manager_bonus=self._manager_bonus,
            ib_bonus=self._ib_bonus,
            non_withdrawable_bonus=self._non_withdrawable_bonus,
            access_rights=self._access_rights,
            deposit_asset_id=self._deposit_asset_id,
            swap_free=self._swap_free,
            leverage_in_cents=self._leverage_in_cents,
            total_margin_calculation_type=self._total_margin_calculation_type,
            max_leverage=self._max_leverage,
            french_risk=self._french_risk,
            trader_login=self._trader_login,
            account_type=self._account_type,
            broker_name=self._broker_name,
            registration_timestamp=self._registration_timestamp,
            is_limited_risk=self._is_limited_risk,
            limited_risk_margin_calculation_strategy=self._limited_risk_margin_calculation_strategy,
            fair_stop_out=self._fair_stop_out,
            stop_out_strategy=self._stop_out_strategy,
        )
        if self._callbacks.on_funds_received:
            self._callbacks.on_funds_received(funds)
        metrics.inc("ctrader.account_funds.success")
        started_at = getattr(self, "_metrics_started_at", None)
        if started_at is not None:
            metrics.observe("ctrader.account_funds.latency_s", time.monotonic() - started_at)
        self._cleanup()

    def _cleanup(self) -> None:
        self._cleanup_request_lifecycle(timeout_tracker=self._timeout_tracker, handler=self._handle_message)

    def _on_timeout(self) -> None:
        if not self._in_progress:
            return
        metrics.inc("ctrader.account_funds.timeout")
        self._emit_error(error_message(ErrorCode.TIMEOUT, "取得帳戶資金逾時"))
        self._cleanup()

    def _retry_request(self, attempt: int) -> None:
        if not self._in_progress:
            return
        self._log(format_warning(f"帳戶資金逾時，重試第 {attempt} 次"))
        metrics.inc("ctrader.account_funds.retry")
        if not self._client or self._account_id is None:
            return
        self._send_initial_requests()

    @staticmethod
    def _scale_money(value: int, digits: int) -> float:
        if digits <= 0:
            return float(value)
        return float(value) / (10 ** digits)
