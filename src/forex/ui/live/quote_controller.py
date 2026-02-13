from __future__ import annotations

from typing import Optional

from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOAPayloadType
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidgetItem

from forex.infrastructure.broker.ctrader.services.spot_subscription import (
    send_spot_subscribe,
    send_spot_unsubscribe,
)


class LiveQuoteController:
    def __init__(self, window) -> None:
        self._window = window

    def ensure_quote_handler(self) -> None:
        w = self._window
        if not w._service:
            return
        if w._spot_message_handler is None:
            w._spot_message_handler = self.handle_spot_message
            w._service.add_message_handler(w._spot_message_handler)

    def ensure_quote_subscription(self) -> None:
        w = self._window
        ready_fn = getattr(w, "_is_broker_runtime_ready", None)
        runtime_ready = bool(ready_fn()) if callable(ready_fn) else True
        if getattr(w, "_account_authorization_blocked", False):
            return
        if not runtime_ready:
            return
        if w._account_switch_in_progress:
            return
        if not w._service or not w._app_state:
            return
        account_id = w._app_state.selected_account_id
        if not account_id:
            return
        w.logRequested.emit(f"➡️ Subscribe quotes (account_id={account_id})")
        try:
            client = w._service.get_client()  # type: ignore[attr-defined]
        except Exception:
            return
        desired_ids = set(w._quote_rows.keys())
        if desired_ids and desired_ids.issubset(w._quote_subscribed_ids | w._quote_subscribe_inflight):
            w._quote_subscribed = True
            return
        self.ensure_quote_handler()

        from forex.utils.reactor_manager import reactor_manager

        reactor_manager.ensure_running()
        from twisted.internet import reactor

        for symbol_id in w._quote_rows.keys():
            if symbol_id in w._quote_subscribed_ids:
                continue
            w._quote_subscribe_inflight.add(symbol_id)
        pending_ids = sorted(w._quote_subscribe_inflight)
        if pending_ids:
            reactor.callFromThread(
                send_spot_subscribe,
                client,
                account_id=account_id,
                symbol_id=pending_ids,
                log=w.logRequested.emit,
                subscribe_to_spot_timestamp=True,
            )
        w._quote_subscribed = True

    def stop_quote_subscription(self) -> None:
        w = self._window
        if not w._service or not w._app_state:
            return
        account_id = w._app_state.selected_account_id
        if not account_id:
            w._quote_subscribed = False
            w._quote_subscribed_ids.clear()
            return
        try:
            client = w._service.get_client()  # type: ignore[attr-defined]
        except Exception:
            w._quote_subscribed = False
            return

        from forex.utils.reactor_manager import reactor_manager

        reactor_manager.ensure_running()
        from twisted.internet import reactor

        unsubscribe_ids = sorted(w._quote_rows.keys())
        if unsubscribe_ids:
            reactor.callFromThread(
                send_spot_unsubscribe,
                client,
                account_id=account_id,
                symbol_id=unsubscribe_ids,
                log=w.logRequested.emit,
            )
        w._quote_subscribed = False
        w._quote_subscribed_ids.clear()
        w._quote_subscribe_inflight.clear()

    def handle_spot_message(self, _client, msg) -> bool:
        w = self._window
        if getattr(msg, "payloadType", None) != ProtoOAPayloadType.PROTO_OA_SPOT_EVENT:
            return False
        account_id = getattr(msg, "ctidTraderAccountId", None)
        if w._app_state and w._app_state.selected_account_id:
            if account_id is not None and int(account_id) != int(w._app_state.selected_account_id):
                return False
        symbol_id = getattr(msg, "symbolId", None)
        if symbol_id is None or symbol_id not in w._quote_rows:
            return False
        if symbol_id in w._quote_subscribe_inflight:
            w._quote_subscribe_inflight.discard(symbol_id)
            w._quote_subscribed_ids.add(symbol_id)
        bid = getattr(msg, "bid", None)
        ask = getattr(msg, "ask", None)
        has_bid = getattr(msg, "hasBid", None)
        has_ask = getattr(msg, "hasAsk", None)
        if has_bid is False:
            bid = None
        if has_ask is False:
            ask = None
        spot_ts = getattr(msg, "spotTimestamp", None)
        if spot_ts is None:
            spot_ts = getattr(msg, "timestamp", None)
        w.quoteUpdated.emit(int(symbol_id), bid, ask, spot_ts)
        return False

    def handle_quote_updated(self, symbol_id: int, bid, ask, spot_ts) -> None:
        w = self._window
        if not w._quotes_table:
            return
        row = w._quote_rows.get(symbol_id)
        if row is None:
            return
        self.set_quote_cell(row, 1, bid)
        self.set_quote_cell(row, 2, ask)
        self.set_quote_extras(row, symbol_id, bid, ask, spot_ts)
        w._update_chart_from_quote(symbol_id, bid, ask, spot_ts)

    def set_quote_cell(self, row: int, column: int, value) -> None:
        w = self._window
        if not w._quotes_table:
            return
        digits = w._quote_row_digits.get(
            next((k for k, v in w._quote_rows.items() if v == row), None),
            w._price_digits,
        )
        normalized = w._normalize_price(value, digits=digits)
        if normalized == 0:
            text = "--"
        else:
            text = w._format_price(value, digits=digits)
        item = w._quotes_table.item(row, column)
        if item is None:
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignCenter)
            w._quotes_table.setItem(row, column, item)
        else:
            item.setText(text)

    def set_quote_extras(self, row: int, symbol_id: int, bid, ask, spot_ts) -> None:
        w = self._window
        if not w._quotes_table:
            return
        digits = w._quote_row_digits.get(int(symbol_id), w._price_digits)
        bid_val = w._normalize_price(bid, digits=digits)
        ask_val = w._normalize_price(ask, digits=digits)
        if bid_val is not None:
            w._quote_last_bid[symbol_id] = bid_val
        if ask_val is not None:
            w._quote_last_ask[symbol_id] = ask_val
        time_text = w._format_spot_time(spot_ts)
        if bid_val in (None, 0) or ask_val in (None, 0):
            self.set_quote_text(row, 3, "--")
            self.set_quote_text(row, 4, time_text)
            return
        mid = (bid_val + ask_val) / 2.0
        w._quote_last_mid[symbol_id] = mid

        digits = w._quote_row_digits.get(symbol_id, w._price_digits)
        spread = ask_val - bid_val
        spread_text = f"{spread:.{digits}f}"
        self.set_quote_text(row, 3, spread_text)
        self.set_quote_text(row, 4, time_text)
        if w._open_positions:
            w._schedule_positions_refresh()

    def set_quote_text(self, row: int, column: int, text: str) -> None:
        w = self._window
        if not w._quotes_table:
            return
        item = w._quotes_table.item(row, column)
        if item is None:
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignCenter)
            w._quotes_table.setItem(row, column, item)
        else:
            item.setText(text)
