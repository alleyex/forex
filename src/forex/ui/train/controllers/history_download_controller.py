from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QWidget

from forex.application.broker.protocols import AppAuthServiceLike, OAuthServiceLike
from forex.application.broker.use_cases import BrokerUseCases
from forex.application.broker.history_download_pipeline import HistoryDownloadPipeline
from forex.config.constants import ConnectionStatus
from forex.config.paths import SYMBOL_LIST_FILE, TIMEFRAMES_FILE, TOKEN_FILE
from forex.config.settings import OAuthTokens
from forex.infrastructure.storage.json_store import read_json, write_json
from forex.ui.train.dialogs.history_download_dialog import HistoryDownloadDialog
from forex.ui.train.state.history_download_state import HistoryDownloadState
from forex.ui.train.presenters.history_download_presenter import HistoryDownloadPresenter
from forex.utils.reactor_manager import reactor_manager


class HistoryDownloadController(QObject):
    DEFAULT_HISTORY_COUNT = 25000
    def __init__(
        self,
        *,
        use_cases: BrokerUseCases,
        app_auth_service: AppAuthServiceLike,
        oauth_service: OAuthServiceLike,
        parent: QWidget,
        state: HistoryDownloadState,
        presenter: HistoryDownloadPresenter,
    ) -> None:
        super().__init__(parent)
        self._use_cases = use_cases
        self._app_auth_service = app_auth_service
        self._oauth_service = oauth_service
        self._state = state
        self._presenter = presenter
        self._download_pipeline: Optional[HistoryDownloadPipeline] = None
        self._dialog: Optional[HistoryDownloadDialog] = None

    def open_download_dialog(self, default_symbol_id: int) -> None:
        account_id = self._get_account_id()
        if account_id is None:
            return

        if self._dialog and self._dialog.isVisible():
            self._dialog.raise_()
            self._dialog.activateWindow()
            return

        self._dialog = HistoryDownloadDialog(default_symbol_id, parent=self.parent())
        self._presenter.set_dialog(self._dialog)
        timeframes = self._ensure_timeframes_list()
        if timeframes:
            self._dialog.set_timeframes(timeframes)

        symbols = self._load_symbol_list()
        if symbols:
            self._dialog.set_symbols(symbols)
        else:
            self._presenter.emit("symbol_list_incomplete")
            self._use_cases.fetch_symbols(
                app_auth_service=self._app_auth_service,
                account_id=account_id,
                on_symbols_received=lambda symbols: QTimer.singleShot(
                    0, self, lambda: self._save_symbol_list(account_id, symbols)
                ),
                on_error=lambda e: self._presenter.emit_async("symbol_list_error", error=e),
                on_log=self._presenter.emit_async_message,
            )

        if self._dialog.exec() != HistoryDownloadDialog.Accepted:
            self._dialog = None
            self._presenter.set_dialog(None)
            return
        params = self._dialog.get_params()
        self._dialog = None
        self._presenter.set_dialog(None)

        pipeline = self._ensure_pipeline()
        minutes = self._timeframe_minutes(params["timeframe"])
        window_minutes = max(1, int((params["to_ts"] - params["from_ts"]) / (60_000 * minutes)))
        count = min(window_minutes, self.DEFAULT_HISTORY_COUNT)

        reactor_manager.ensure_running()
        from twisted.internet import reactor
        reactor.callFromThread(
            pipeline.fetch_to_raw,
            account_id,
            params["symbol_id"],
            count,
            timeframe=params["timeframe"],
            from_ts=params["from_ts"],
            to_ts=params["to_ts"],
            output_path=params["output_path"],
            on_saved=lambda path: self._presenter.emit_async("history_saved", path=path),
            on_error=lambda e: self._presenter.emit_async("history_error", error=e),
            on_log=self._presenter.emit_async_message,
        )

    def _get_account_id(self) -> Optional[int]:
        if not self._app_auth_service:
            self._presenter.emit("app_auth_missing")
            return None
        if not self._app_auth_service.is_app_authenticated:
            self._presenter.emit("app_auth_disconnected")
            return None
        if not self._oauth_service or self._oauth_service.status != ConnectionStatus.ACCOUNT_AUTHENTICATED:
            self._presenter.emit("oauth_missing")
            return None

        try:
            tokens = OAuthTokens.from_file(TOKEN_FILE)
        except Exception as exc:
            self._presenter.emit("token_read_failed", error=exc)
            return None
        if not tokens.account_id:
            self._presenter.emit("account_id_missing")
            return None
        return tokens.account_id

    def _ensure_pipeline(self) -> HistoryDownloadPipeline:
        if self._download_pipeline is None:
            self._download_pipeline = HistoryDownloadPipeline(
                broker_use_cases=self._use_cases,
                app_auth_service=self._app_auth_service,
            )
        return self._download_pipeline

    def _save_symbol_list(self, account_id: int, symbols: list) -> None:
        if not symbols:
            self._presenter.emit("symbol_list_empty")
            return
        payload = []
        for symbol in symbols:
            if isinstance(symbol, dict):
                symbol_id = symbol.get("symbol_id")
                symbol_name = symbol.get("symbol_name") or symbol.get("name")
                extra = {
                    k: symbol.get(k)
                    for k in ("min_volume", "max_volume", "volume_step", "lot_size", "digits")
                    if k in symbol
                }
            else:
                symbol_id = getattr(symbol, "symbol_id", None)
                symbol_name = getattr(symbol, "name", None)
                extra = {
                    "min_volume": getattr(symbol, "min_volume", None),
                    "max_volume": getattr(symbol, "max_volume", None),
                    "volume_step": getattr(symbol, "volume_step", None),
                    "lot_size": getattr(symbol, "lot_size", None),
                    "digits": getattr(symbol, "digits", None),
                }
            if symbol_id is None or symbol_name is None:
                continue
            item = {
                "symbol_id": int(symbol_id),
                "symbol_name": str(symbol_name),
            }
            for key, value in extra.items():
                if value is not None:
                    item[key] = value
            payload.append(item)
        path = self._symbol_list_path()
        self._presenter.emit(
            "symbol_list_write_start",
            path=path.resolve(),
            count=len(payload),
        )
        try:
            write_json(path, payload)
        except Exception as exc:
            self._presenter.emit("symbol_list_write_failed", error=exc)
            return
        self._presenter.emit("symbol_list_saved", path=path.resolve())
        self._presenter.update_symbols(payload)

    @staticmethod
    def _load_symbol_list() -> list:
        path = Path.cwd() / SYMBOL_LIST_FILE
        fallback = Path(".symbol.json")
        if not path.exists() and fallback.exists():
            path = fallback
        if not path.exists():
            return []
        raw = read_json(path, []) or []
        if not isinstance(raw, list):
            return []
        symbols: list[dict] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            symbol_id = item.get("symbol_id")
            symbol_name = item.get("symbol_name")
            if not isinstance(symbol_id, int):
                continue
            if not isinstance(symbol_name, str) or not symbol_name.strip():
                continue
            keep = {
                "symbol_id": symbol_id,
                "symbol_name": symbol_name,
            }
            for key in ("min_volume", "max_volume", "volume_step", "lot_size", "digits"):
                if key in item:
                    keep[key] = item[key]
            symbols.append(keep)
        return symbols

    @staticmethod
    def _symbol_list_path() -> Path:
        return Path.cwd() / SYMBOL_LIST_FILE

    @staticmethod
    def _timeframes_path() -> Path:
        return Path.cwd() / TIMEFRAMES_FILE

    def _ensure_timeframes_list(self) -> list[str]:
        path = self._timeframes_path()
        raw = read_json(path, [])
        timeframes = [item for item in raw if isinstance(item, str) and item.strip()]
        if not timeframes:
            timeframes = [
                "M1",
                "M2",
                "M3",
                "M4",
                "M5",
                "M10",
                "M15",
                "M30",
                "H1",
                "H4",
                "H12",
                "D1",
                "W1",
                "MN1",
            ]
            try:
                write_json(path, timeframes)
            except Exception as exc:
                self._presenter.emit("timeframes_write_failed", error=exc)
        return timeframes

    @staticmethod
    def _timeframe_minutes(timeframe: str) -> int:
        return {
            "M1": 1,
            "M5": 5,
            "M10": 10,
            "M15": 15,
            "H1": 60,
        }.get(timeframe.upper(), 5)
