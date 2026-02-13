from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QMetaObject, Qt, QThread, Slot
from PySide6.QtWidgets import QApplication


class LiveSymbolListService:
    """Handles symbol list refresh/apply and trade-symbol combo synchronization."""

    def __init__(self, window) -> None:
        self._window = window

    def queue_symbol_list_apply(self, symbols: list) -> None:
        w = self._window
        w._pending_symbol_list = symbols
        app = QApplication.instance()
        if app is not None and QThread.currentThread() == app.thread():
            self.apply_symbol_list_update()
            return
        QMetaObject.invokeMethod(w, "_apply_symbol_list_update", Qt.QueuedConnection)

    @Slot()
    def apply_symbol_list_update(self) -> None:
        w = self._window
        symbols = w._pending_symbol_list or []
        if not symbols:
            return
        names = []
        mapping = {}
        for item in symbols:
            name = item.get("symbol_name") if isinstance(item, dict) else None
            symbol_id = item.get("symbol_id") if isinstance(item, dict) else None
            if not name or symbol_id is None:
                continue
            if name in mapping:
                continue
            try:
                mapping[name] = int(symbol_id)
            except (TypeError, ValueError):
                continue
            names.append(name)
        w._symbol_names = names
        w._symbol_id_map = mapping
        w._symbol_id_to_name = {symbol_id: name for name, symbol_id in mapping.items()}
        w._fx_symbols = w._filter_fx_symbols(w._symbol_names)
        current = w._trade_symbol.currentText()
        self.sync_trade_symbol_choices(preferred_symbol=current)
        w._auto_log(f"✅ Symbol list refreshed: {len(w._fx_symbols)} symbols")
        current_symbol = w._trade_symbol.currentText() if hasattr(w, "_trade_symbol") else ""
        if not current_symbol:
            current_symbol = w._symbol_name

    def trade_symbol_choices(self) -> list[str]:
        w = self._window
        choices: list[str] = []
        for symbol in w._quote_symbols:
            if isinstance(symbol, str) and symbol and symbol not in choices:
                choices.append(symbol)
        if choices:
            return choices
        return ["EURUSD", "USDJPY"]

    def sync_trade_symbol_choices(self, preferred_symbol: Optional[str] = None) -> None:
        w = self._window
        if not hasattr(w, "_trade_symbol") or w._trade_symbol is None:
            return
        combo = w._trade_symbol
        choices = self.trade_symbol_choices()
        current = preferred_symbol or combo.currentText() or w._symbol_name
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(choices)
        if current in choices:
            target = current
        elif w._symbol_name in choices:
            target = w._symbol_name
        else:
            target = choices[0]
        combo.setCurrentText(target)
        combo.blockSignals(False)
        if target and target != w._symbol_name:
            w._symbol_name = target
            w._symbol_id = w._resolve_symbol_id(target)
