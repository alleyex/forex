from __future__ import annotations

import json


class LiveSymbolController:
    def __init__(self, window) -> None:
        self._window = window

    def resolve_symbol_id(self, symbol_name: str) -> int:
        w = self._window
        if symbol_name in w._symbol_id_map:
            return w._symbol_id_map[symbol_name]
        path = w._symbol_list_path()
        if not path.exists():
            return 1
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return 1
        for item in data:
            if item.get("symbol_name") == symbol_name:
                try:
                    return int(item.get("symbol_id", 1))
                except (TypeError, ValueError):
                    return 1
        return 1

    def handle_trade_symbol_changed(self, symbol: str) -> None:
        w = self._window
        ready_fn = getattr(w, "_is_broker_runtime_ready", None)
        runtime_ready = bool(ready_fn()) if callable(ready_fn) else True
        if not symbol:
            return
        if w._account_switch_in_progress:
            return
        if symbol != w._symbol_name:
            w._symbol_name = symbol
            w._symbol_id = self.resolve_symbol_id(symbol)
            w._price_digits = w._quote_digits.get(symbol, self.infer_quote_digits(symbol))
            w._stop_live_trendbar()
            # Clear previous symbol chart immediately to avoid transient mixed-scale spikes.
            w._chart_frozen = True
            w._awaiting_history_after_symbol_change = True
            w._candles = []
            w.set_candles([])
            w._flush_chart_update()
        w._history_requested = False
        w._pending_history = False
        w._last_history_request_key = None
        w._last_history_success_key = None
        if runtime_ready:
            w._request_recent_history()
        else:
            # No authenticated history fetch path yet; allow quote bootstrap.
            w._awaiting_history_after_symbol_change = False

    def fetch_symbol_details(self, symbol_name: str) -> None:
        w = self._window
        if w._account_switch_in_progress:
            return
        if not w._service or not w._app_state or not w._app_state.selected_account_id:
            return
        symbol_id = int(self.resolve_symbol_id(symbol_name))
        if symbol_id <= 0:
            return
        if symbol_id in w._symbol_details_by_id:
            return
        if symbol_id in w._symbol_details_unavailable:
            return
        if w._symbol_by_id_uc is None:
            try:
                w._symbol_by_id_uc = w._use_cases.create_symbol_by_id(w._service)
            except Exception:
                return
        if getattr(w._symbol_by_id_uc, "in_progress", False):
            return

        account_id = int(w._app_state.selected_account_id)
        w.logRequested.emit(f"➡️ Request symbol details (account_id={account_id}, symbol_id={symbol_id})")

        def _on_symbols(symbols: list) -> None:
            if not symbols:
                return
            merged = self.merge_symbol_details(symbols)
            if not merged:
                w._symbol_details_unavailable.add(symbol_id)

        w._symbol_by_id_uc.set_callbacks(
            on_symbols_received=_on_symbols,
            on_error=lambda e: w._auto_log(f"❌ Symbol detail error: {e}"),
            on_log=w._auto_log,
        )
        w._symbol_by_id_uc.fetch(
            account_id=account_id,
            symbol_ids=[symbol_id],
            include_archived=False,
        )

    def merge_symbol_details(self, symbols: list[dict]) -> bool:
        w = self._window
        path = w._symbol_list_path()
        existing: list[dict] = []
        if path.exists():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                existing = []

        by_id: dict[int, dict] = {}
        by_name: dict[str, dict] = {}
        for item in existing:
            if not isinstance(item, dict):
                continue
            sid = item.get("symbol_id")
            name = item.get("symbol_name")
            if isinstance(sid, int):
                by_id[sid] = item
            if isinstance(name, str) and name:
                by_name[name] = item

        updated = False
        merged_any = False
        for detail in symbols:
            if not isinstance(detail, dict):
                continue
            extra_keys = set(detail.keys()) - {"symbol_id", "symbol_name"}
            if not extra_keys:
                continue
            sid = detail.get("symbol_id")
            name = detail.get("symbol_name")
            if not isinstance(name, str) or not name.strip():
                if isinstance(sid, int):
                    w._symbol_details_by_id[sid] = detail
                continue
            target = None
            if isinstance(sid, int):
                target = by_id.get(sid)
            if target is None and isinstance(name, str) and name:
                target = by_name.get(name)
            if target is None:
                if not existing:
                    if isinstance(sid, int):
                        w._symbol_details_by_id[sid] = detail
                    continue
                target = {"symbol_id": sid, "symbol_name": name}
                existing.append(target)
                if isinstance(sid, int):
                    by_id[sid] = target
                by_name[name] = target
            for key, value in detail.items():
                if value is None:
                    continue
                if target.get(key) != value:
                    target[key] = value
                    updated = True
            merged_any = True
            if isinstance(sid, int):
                w._symbol_details_by_id[sid] = detail
            if isinstance(name, str) and name:
                min_volume = detail.get("min_volume")
                volume_step = detail.get("volume_step")
                try:
                    min_volume_int = int(min_volume) if min_volume is not None else None
                except (TypeError, ValueError):
                    min_volume_int = None
                try:
                    volume_step_int = int(volume_step) if volume_step is not None else None
                except (TypeError, ValueError):
                    volume_step_int = None
                if min_volume_int is not None or volume_step_int is not None:
                    if min_volume_int is None:
                        min_volume_int = max(1, volume_step_int or 1)
                    if volume_step_int is None:
                        volume_step_int = min_volume_int
                    if min_volume_int > 0 and volume_step_int > 0:
                        w._symbol_volume_constraints[name] = (min_volume_int, volume_step_int)
                        w._symbol_volume_loaded = True
                digits = detail.get("digits")
                if isinstance(digits, int) and digits > 0:
                    w._symbol_digits_by_name[name] = digits
                    w._quote_digits[name] = digits
                    current_symbol = w._trade_symbol.currentText() if hasattr(w, "_trade_symbol") else ""
                    if not current_symbol:
                        current_symbol = w._symbol_name
                    if name == current_symbol:
                        w._price_digits = digits
                    if isinstance(sid, int):
                        w._quote_row_digits[sid] = digits

        if updated:
            try:
                path.write_text(json.dumps(existing, ensure_ascii=True, indent=2), encoding="utf-8")
            except Exception:
                pass
        return merged_any

    def load_symbol_catalog(self) -> tuple[list[str], dict[str, int]]:
        w = self._window
        path = w._symbol_list_path()
        if not path.exists():
            return [], {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return [], {}
        names: list[str] = []
        mapping: dict[str, int] = {}
        for item in data:
            name = item.get("symbol_name")
            if not isinstance(name, str) or not name:
                continue
            if name in mapping:
                continue
            try:
                symbol_id = int(item.get("symbol_id", 1))
            except (TypeError, ValueError):
                symbol_id = 1
            mapping[name] = symbol_id
            names.append(name)
        return names, mapping

    @staticmethod
    def filter_fx_symbols(names: list[str]) -> list[str]:
        return [name for name in names if len(name) == 6 and name.isalpha() and name.isupper()]

    def default_quote_symbols(self) -> list[str]:
        w = self._window
        preferred = ("EURUSD", "USDJPY", "GBPUSD", "AUDUSD")
        defaults = [name for name in preferred if name in w._symbol_id_map]
        if defaults:
            return defaults[: w._max_quote_rows]
        if w._fx_symbols:
            return w._fx_symbols[: w._max_quote_rows]
        return list(preferred[: w._max_quote_rows])

    @staticmethod
    def infer_quote_digits(symbol: str) -> int:
        if symbol.endswith("JPY"):
            return 3
        return 5

    def sync_quote_symbols(self, symbol: str) -> None:
        w = self._window
        next_symbols = [symbol] + [item for item in w._quote_symbols if item != symbol]
        self.set_quote_symbols(next_symbols[: w._max_quote_rows])

    def set_quote_symbols(self, symbols: list[str]) -> None:
        w = self._window
        unique: list[str] = []
        for symbol in symbols:
            if symbol and symbol not in unique:
                unique.append(symbol)
        if not unique:
            return
        if unique == w._quote_symbols:
            return
        was_subscribed = w._quote_subscribed
        if was_subscribed:
            w._stop_quote_subscription()
        w._quote_symbols = unique
        w._quote_symbol_ids = {name: self.resolve_symbol_id(name) for name in w._quote_symbols}
        w._quote_rows.clear()
        w._quote_row_digits.clear()
        w._quote_last_mid.clear()
        w._quote_subscribed_ids.clear()
        sync_trade_symbols = getattr(w, "_sync_trade_symbol_choices", None)
        if callable(sync_trade_symbols):
            sync_trade_symbols()
        if w._quotes_table:
            self.rebuild_quotes_table()
        if was_subscribed:
            w._ensure_quote_subscription()

    def rebuild_quotes_table(self) -> None:
        w = self._window
        if not w._quotes_table:
            return
        table = w._quotes_table
        rows = max(1, len(w._quote_symbols))
        table.setRowCount(rows)
        for row in range(rows):
            for col in range(5):
                item = table.item(row, col)
                if item is None:
                    from PySide6.QtCore import Qt
                    from PySide6.QtWidgets import QTableWidgetItem

                    item = QTableWidgetItem("-")
                    item.setTextAlignment(Qt.AlignCenter)
                    table.setItem(row, col, item)

        for row, symbol in enumerate(w._quote_symbols):
            symbol_item = table.item(row, 0)
            if symbol_item is None:
                from PySide6.QtCore import Qt
                from PySide6.QtWidgets import QTableWidgetItem

                symbol_item = QTableWidgetItem(symbol)
                symbol_item.setTextAlignment(Qt.AlignCenter)
                table.setItem(row, 0, symbol_item)
            else:
                symbol_item.setText(symbol)
            for col in (1, 2, 3, 4):
                cell = table.item(row, col)
                if cell is None:
                    from PySide6.QtCore import Qt
                    from PySide6.QtWidgets import QTableWidgetItem

                    cell = QTableWidgetItem("-")
                    cell.setTextAlignment(Qt.AlignCenter)
                    table.setItem(row, col, cell)
                else:
                    cell.setText("-")
            symbol_id = w._quote_symbol_ids.get(symbol)
            if symbol_id is not None:
                w._quote_rows[symbol_id] = row
                w._quote_row_digits[symbol_id] = w._quote_digits.get(symbol, self.infer_quote_digits(symbol))
