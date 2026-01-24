from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QWidget

from application import AppAuthServiceLike, BrokerUseCases, OAuthServiceLike
from application.broker.history_download_pipeline import HistoryDownloadPipeline
from config.constants import ConnectionStatus
from config.paths import SYMBOL_LIST_FILE, TIMEFRAMES_FILE, TOKEN_FILE
from config.settings import OAuthTokens
from infrastructure.storage.json_store import read_json, write_json
from ui.dialogs.history_download_dialog import HistoryDownloadDialog
from utils.reactor_manager import reactor_manager


class HistoryDownloadController(QObject):
    DEFAULT_HISTORY_COUNT = 100000
    def __init__(
        self,
        *,
        use_cases: BrokerUseCases,
        app_auth_service: AppAuthServiceLike,
        oauth_service: OAuthServiceLike,
        parent: QWidget,
        log: Callable[[str], None],
        log_async: Callable[[str], None],
    ) -> None:
        super().__init__(parent)
        self._use_cases = use_cases
        self._app_auth_service = app_auth_service
        self._oauth_service = oauth_service
        self._log = log
        self._log_async = log_async
        self._download_pipeline: Optional[HistoryDownloadPipeline] = None
        self._dialog: Optional[HistoryDownloadDialog] = None

    def request_quick_download(self, symbol_id: int, *, timeframe: str = "M5") -> None:
        account_id = self._get_account_id()
        if account_id is None:
            return

        pipeline = self._ensure_pipeline()
        bars_per_day = 24 * 12
        two_years_bars = 365 * 2 * bars_per_day
        now_ms = int(time.time() * 1000)
        from_ts = now_ms - int(two_years_bars * 5 * 60 * 1000)

        reactor_manager.ensure_running()
        from twisted.internet import reactor
        reactor.callFromThread(
            pipeline.fetch_to_raw,
            account_id,
            symbol_id,
            self.DEFAULT_HISTORY_COUNT,
            timeframe=timeframe,
            from_ts=from_ts,
            to_ts=now_ms,
            on_saved=lambda path: self._log_async(f"✅ 已儲存歷史資料：{path}"),
            on_error=lambda e: self._log_async(f"⚠️ 歷史資料錯誤: {e}"),
            on_log=self._log_async,
        )

    def open_download_dialog(self, default_symbol_id: int) -> None:
        account_id = self._get_account_id()
        if account_id is None:
            return

        if self._dialog and self._dialog.isVisible():
            self._dialog.raise_()
            self._dialog.activateWindow()
            return

        self._dialog = HistoryDownloadDialog(default_symbol_id, parent=self.parent())
        timeframes = self._ensure_timeframes_list()
        if timeframes:
            self._dialog.set_timeframes(timeframes)

        symbols = self._load_symbol_list()
        if symbols:
            self._dialog.set_symbols(symbols)
        else:
            self._log("📥 symbol list 不完整，正在重新取得...")
            self._use_cases.fetch_symbols(
                app_auth_service=self._app_auth_service,
                account_id=account_id,
                on_symbols_received=lambda symbols: QTimer.singleShot(
                    0, self, lambda: self._save_symbol_list(account_id, symbols)
                ),
                on_error=lambda e: self._log_async(f"⚠️ symbol list 錯誤: {e}"),
                on_log=self._log_async,
            )

        if self._dialog.exec() != HistoryDownloadDialog.Accepted:
            self._dialog = None
            return
        params = self._dialog.get_params()
        self._dialog = None

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
            on_saved=lambda path: self._log_async(f"✅ 已儲存歷史資料：{path}"),
            on_error=lambda e: self._log_async(f"⚠️ 歷史資料錯誤: {e}"),
            on_log=self._log_async,
        )

    def request_symbol_list(self) -> None:
        account_id = self._get_account_id()
        if account_id is None:
            return

        self._log("📥 正在取得 symbol list...")
        self._use_cases.fetch_symbols(
            app_auth_service=self._app_auth_service,
            account_id=account_id,
            on_symbols_received=lambda symbols: QTimer.singleShot(
                0, self, lambda: self._save_symbol_list(account_id, symbols)
            ),
            on_error=lambda e: self._log_async(f"⚠️ symbol list 錯誤: {e}"),
            on_log=self._log_async,
        )

    def _get_account_id(self) -> Optional[int]:
        if not self._app_auth_service:
            self._log("⚠️ 尚未完成 App 認證")
            return None
        if not self._app_auth_service.is_app_authenticated:
            self._log("⚠️ App 認證已中斷，請稍候自動重連")
            return None
        if not self._oauth_service or self._oauth_service.status != ConnectionStatus.ACCOUNT_AUTHENTICATED:
            self._log("⚠️ 尚未完成 OAuth 帳戶認證")
            return None

        try:
            tokens = OAuthTokens.from_file(TOKEN_FILE)
        except Exception as exc:
            self._log(f"⚠️ 無法讀取 OAuth Token: {exc}")
            return None
        if not tokens.account_id:
            self._log("⚠️ 缺少帳戶 ID")
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
            self._log("⚠️ symbol list 為空")
            return
        payload = []
        for symbol in symbols:
            if isinstance(symbol, dict):
                symbol_id = symbol.get("symbol_id")
                symbol_name = symbol.get("symbol_name") or symbol.get("name")
            else:
                symbol_id = getattr(symbol, "symbol_id", None)
                symbol_name = getattr(symbol, "name", None)
            if symbol_id is None or symbol_name is None:
                continue
            payload.append(
                {
                    "symbol_id": int(symbol_id),
                    "symbol_name": str(symbol_name),
                }
            )
        path = self._symbol_list_path()
        self._log(f"📦 正在寫入 symbol list：{path.resolve()} ({len(payload)} 筆)")
        try:
            write_json(path, payload)
        except Exception as exc:
            self._log(f"⚠️ 無法寫入 symbol list: {exc}")
            return
        self._log(f"✅ 已儲存 symbol list：{path.resolve()}")
        if self._dialog and self._dialog.isVisible():
            self._dialog.set_symbols(payload)

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
            symbols.append({"symbol_id": symbol_id, "symbol_name": symbol_name})
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
                self._log(f"⚠️ 無法寫入 timeframes.json: {exc}")
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
