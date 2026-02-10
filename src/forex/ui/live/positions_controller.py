from __future__ import annotations

from typing import Optional

from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAReconcileReq
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOAPayloadType, ProtoOATradeSide
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidgetItem


class LivePositionsController:
    def __init__(self, window) -> None:
        self._window = window

    def ensure_positions_handler(self) -> None:
        w = self._window
        if not w._service:
            return
        if w._positions_message_handler is None:
            w._positions_message_handler = w._handle_positions_message
            w._service.add_message_handler(w._positions_message_handler)

    def request_positions(self) -> None:
        w = self._window
        if w._account_switch_in_progress:
            return
        if not w._service or not w._app_state:
            return
        account_id = w._app_state.selected_account_id
        if not account_id:
            return
        w.logRequested.emit(f"➡️ Request positions (account_id={account_id})")
        try:
            client = w._service.get_client()  # type: ignore[attr-defined]
        except Exception:
            return
        self.ensure_positions_handler()
        request = ProtoOAReconcileReq()
        request.ctidTraderAccountId = int(account_id)
        client.send(request)

    def handle_positions_message(self, _client, msg) -> bool:
        w = self._window
        if getattr(msg, "payloadType", None) != ProtoOAPayloadType.PROTO_OA_RECONCILE_RES:
            return False
        account_id = getattr(msg, "ctidTraderAccountId", None)
        if w._app_state and w._app_state.selected_account_id:
            if int(account_id or 0) != int(w._app_state.selected_account_id):
                return False
        positions = list(getattr(msg, "position", []))
        w.positionsUpdated.emit(positions)
        return False

    def apply_positions_update(self, positions: object) -> None:
        w = self._window
        try:
            pos_list = list(positions) if positions is not None else []
        except Exception:
            pos_list = []
        w._open_positions = pos_list
        w._sync_auto_position_from_positions(pos_list)
        self.schedule_positions_refresh()

    def update_positions_table(self, positions: list[object]) -> None:
        w = self._window
        if not w._positions_table:
            return
        table = w._positions_table
        table.setRowCount(len(positions))
        for row, position in enumerate(positions):
            trade_data = getattr(position, "tradeData", None)
            symbol_id = getattr(trade_data, "symbolId", None) if trade_data else None
            symbol_name = w._symbol_id_to_name.get(int(symbol_id)) if symbol_id else "-"
            side_value = getattr(trade_data, "tradeSide", None) if trade_data else None
            if side_value == ProtoOATradeSide.BUY:
                side_text = "BUY"
            elif side_value == ProtoOATradeSide.SELL:
                side_text = "SELL"
            else:
                side_text = "-"
            volume = getattr(trade_data, "volume", None) if trade_data else None
            if volume is not None:
                try:
                    lot_text = f"{self.volume_to_lots(float(volume)):.2f}"
                except (TypeError, ValueError):
                    lot_text = "-"
            else:
                lot_text = "-"
            entry_price = getattr(position, "price", None)
            entry_text = w._format_price(entry_price) if entry_price is not None else "-"
            current_text = w._current_price_text(symbol_id=symbol_id, side_value=side_value)
            sl_price = getattr(position, "stopLoss", None)
            tp_price = getattr(position, "takeProfit", None)
            sl_text = w._format_price(sl_price) if sl_price not in (None, 0) else "-"
            tp_text = w._format_price(tp_price) if tp_price not in (None, 0) else "-"
            open_ts = getattr(trade_data, "openTimestamp", None) if trade_data else None
            time_text = w._format_time(open_ts) if open_ts is not None else "-"
            pnl_text = self.calc_position_pnl(
                position=position,
                trade_data=trade_data,
                symbol_id=symbol_id,
                side_value=side_value,
                entry_price=entry_price,
                volume=volume,
            )

            position_id = getattr(position, "positionId", None)
            values = [
                symbol_name or "-",
                side_text,
                lot_text,
                entry_text,
                current_text,
                pnl_text,
                sl_text,
                tp_text,
                time_text,
                position_id if position_id is not None else "-",
            ]
            for col, value in enumerate(values):
                item = table.item(row, col)
                if item is None:
                    item = QTableWidgetItem(str(value))
                    item.setTextAlignment(Qt.AlignCenter)
                    table.setItem(row, col, item)
                else:
                    item.setText(str(value))

    def schedule_positions_refresh(self) -> None:
        w = self._window
        if w._positions_refresh_pending:
            return
        w._positions_refresh_pending = True
        w._positions_refresh_timer.start()

    def apply_positions_refresh(self) -> None:
        w = self._window
        w._positions_refresh_pending = False
        if w._open_positions:
            self.update_positions_table(w._open_positions)

    @staticmethod
    def volume_to_lots(volume_value: float) -> float:
        return volume_value / 10000000.0

    def calc_position_pnl(
        self,
        *,
        position: Optional[object],
        trade_data: Optional[object],
        symbol_id: Optional[int],
        side_value: Optional[int],
        entry_price,
        volume,
    ) -> str:
        w = self._window
        # Prefer live quotes for real-time updates, fall back to cached/embedded PnL.
        if symbol_id is not None and entry_price is not None and volume is not None:
            try:
                entry = float(entry_price)
                vol = float(volume)
            except (TypeError, ValueError):
                entry = None
                vol = None
            if entry and vol and entry > 0 and vol > 0:
                bid = w._quote_last_bid.get(int(symbol_id))
                ask = w._quote_last_ask.get(int(symbol_id))
                mid = w._quote_last_mid.get(int(symbol_id))
                if side_value == ProtoOATradeSide.BUY:
                    current = bid if bid else mid
                elif side_value == ProtoOATradeSide.SELL:
                    current = ask if ask else mid
                else:
                    current = None
                if current is not None:
                    pnl = (current - entry) * vol if side_value == ProtoOATradeSide.BUY else (entry - current) * vol
                    return f"{pnl:,.2f}"

        position_id = getattr(position, "positionId", None)
        if position_id is not None:
            cached = w._position_pnl_by_id.get(int(position_id))
            if cached is not None:
                return f"{cached:,.2f}"
        for source in (position, trade_data):
            if source is None:
                continue
            money_digits = getattr(source, "moneyDigits", None) or getattr(position, "moneyDigits", None)
            for attr in ("netProfit", "netUnrealizedPnl", "unrealizedPnl", "profit", "grossProfit", "pnl"):
                value = getattr(source, attr, None)
                if value is None:
                    continue
                try:
                    if money_digits is not None and isinstance(value, int):
                        scaled = w._scale_money(value, int(money_digits))
                        return f"{scaled:,.2f}"
                    return f"{float(value):,.2f}"
                except (TypeError, ValueError):
                    pass
        if symbol_id is None or entry_price is None or volume is None:
            return "-"
        try:
            entry = float(entry_price)
            vol = float(volume)
        except (TypeError, ValueError):
            return "-"
        if vol <= 0 or entry <= 0:
            return "-"
        bid = w._quote_last_bid.get(int(symbol_id))
        ask = w._quote_last_ask.get(int(symbol_id))
        mid = w._quote_last_mid.get(int(symbol_id))
        if side_value == ProtoOATradeSide.BUY:
            current = bid if bid else mid
            if current is None:
                return "-"
            pnl = (current - entry) * vol
        elif side_value == ProtoOATradeSide.SELL:
            current = ask if ask else mid
            if current is None:
                return "-"
            pnl = (entry - current) * vol
        else:
            return "-"
        return f"{pnl:,.2f}"
