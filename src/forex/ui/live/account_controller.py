from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

from forex.config.paths import TOKEN_FILE


class LiveAccountController:
    def __init__(self, window) -> None:
        self._window = window

    def refresh_account_balance(self) -> None:
        w = self._window
        if w._account_switch_in_progress:
            return
        if not w._service or not w._app_state or not w._app_state.selected_account_id:
            return
        now = time.time()
        if now - w._last_funds_fetch_ts < 4.5:
            return
        account_id = int(w._app_state.selected_account_id)
        try:
            if getattr(w, "_account_funds_uc", None) is None:
                w._account_funds_uc = w._use_cases.create_account_funds(w._service)
            funds_uc = w._account_funds_uc
            if getattr(funds_uc, "in_progress", False):
                return
        except Exception:
            return
        w._last_funds_fetch_ts = now

        def _on_funds(snapshot) -> None:
            balance = getattr(snapshot, "balance", None)
            if balance is not None:
                w._auto_balance = float(balance)
                if w._auto_peak_balance is None or w._auto_balance > w._auto_peak_balance:
                    w._auto_peak_balance = w._auto_balance
                day_key = datetime.utcnow().strftime("%Y-%m-%d")
                if w._auto_day_key != day_key:
                    w._auto_day_key = day_key
                    w._auto_day_balance = w._auto_balance
            w.logRequested.emit("✅ Funds received")
            w.accountSummaryUpdated.emit(snapshot)

        def _on_position_pnl(pnl_map: dict[int, float]) -> None:
            if pnl_map:
                w._position_pnl_by_id.update(pnl_map)
                if w._open_positions:
                    w.positionsUpdated.emit(w._open_positions)

        funds_uc.set_callbacks(
            on_funds_received=_on_funds,
            on_position_pnl=_on_position_pnl,
            on_log=w.logRequested.emit,
        )
        funds_uc.fetch(account_id)

    def refresh_accounts(self) -> None:
        w = self._window
        if not w._use_cases:
            w.logRequested.emit("⚠️ Missing use cases.")
            return
        if not w._service:
            w.logRequested.emit("⚠️ App auth service unavailable. Cannot fetch accounts.")
            return
        if w._use_cases.account_list_in_progress():
            w.logRequested.emit("⏳ 正在取得帳戶列表，請稍候")
            return

        tokens = w._load_tokens_for_accounts()
        access_token = "" if tokens is None else str(tokens.access_token or "").strip()
        if not access_token:
            w.logRequested.emit("⚠️ 缺少 Access Token，請先完成 OAuth 授權")
            return

        from forex.utils.reactor_manager import reactor_manager

        reactor_manager.ensure_running()
        from twisted.internet import reactor

        reactor.callFromThread(
            w._use_cases.fetch_accounts,
            w._service,
            access_token,
            w._handle_accounts_received,
            w._handle_accounts_error,
            w.logRequested.emit,
        )

    def handle_accounts_received(self, accounts: list[object]) -> None:
        w = self._window
        w._accounts = list(accounts or [])
        if w._accounts:
            try:
                raw_items = []
                for item in w._accounts:
                    if isinstance(item, dict):
                        raw_items.append(item)
                    else:
                        raw_items.append(
                            {
                                "account_id": getattr(item, "account_id", None),
                                "is_live": getattr(item, "is_live", None),
                                "trader_login": getattr(item, "trader_login", None),
                                "permission_scope": getattr(item, "permission_scope", None),
                            }
                        )
                w.logRequested.emit(f"✅ Accounts received: {raw_items}")
            except Exception as exc:
                w.logRequested.emit(f"⚠️ Failed to format accounts: {exc}")
        if not w._account_combo:
            return

        preferred_id = None
        if w._app_state and w._app_state.selected_account_id:
            preferred_id = int(w._app_state.selected_account_id)
        else:
            tokens = w._load_tokens_for_accounts()
            if tokens and tokens.account_id:
                try:
                    preferred_id = int(tokens.account_id)
                except Exception:
                    preferred_id = None

        w._account_combo.blockSignals(True)
        w._account_combo.clear()
        w._account_combo.addItem("Select account", None)

        selected_index = 0
        for idx, account in enumerate(w._accounts, start=1):
            account_id = getattr(account, "account_id", None)
            if isinstance(account, dict):
                account_id = account.get("account_id")
            if not account_id:
                continue
            w._account_combo.addItem(self._account_label(account), int(account_id))
            if preferred_id is not None and int(account_id) == int(preferred_id):
                selected_index = idx

        w._account_combo.setCurrentIndex(selected_index)
        w._account_combo.blockSignals(False)

        selected_id = w._account_combo.currentData()
        if selected_id is not None:
            self.apply_selected_account(
                int(selected_id),
                save_token=False,
                log=False,
                user_initiated=False,
            )

    def handle_accounts_error(self, error: str) -> None:
        self._window.logRequested.emit(f"❌ Account list error: {error}")

    def handle_account_combo_changed(self, index: int) -> None:
        w = self._window
        if not w._account_combo:
            return
        account_id = w._account_combo.itemData(index)
        if account_id is None:
            return
        if int(account_id) in w._unauthorized_accounts:
            w.logRequested.emit(f"⚠️ Account {account_id} is not authorized for Open API.")
            if w._last_authorized_account_id:
                self.sync_account_combo(int(w._last_authorized_account_id))
            return
        self.apply_selected_account(int(account_id), save_token=True, log=True, user_initiated=True)

    def apply_selected_account(
        self,
        account_id: int,
        *,
        save_token: bool,
        log: bool,
        user_initiated: bool,
    ) -> None:
        w = self._window
        if not w._app_state:
            return
        current = w._app_state.selected_account_id
        if current is not None and int(current) == int(account_id):
            return
        scope = self.resolve_account_scope(int(account_id))
        w._app_state.set_selected_account(int(account_id), scope)
        if save_token:
            tokens = w._load_tokens_for_accounts()
            if tokens:
                tokens.account_id = int(account_id)
                try:
                    tokens.save(TOKEN_FILE)
                except Exception as exc:
                    w.logRequested.emit(f"⚠️ 無法寫入 token 檔案: {exc}")
        if log:
            w.logRequested.emit(f"✅ 已選擇帳戶: {account_id}")
        if user_initiated:
            w._account_switch_in_progress = True
            w.logRequested.emit("🔁 帳戶已切換，正在重新連線以完成授權")
            w._schedule_full_reconnect()

    def resolve_account_scope(self, account_id: int) -> Optional[int]:
        w = self._window
        for account in w._accounts:
            if isinstance(account, dict):
                acct_id = account.get("account_id")
                scope = account.get("permission_scope")
            else:
                acct_id = getattr(account, "account_id", None)
                scope = getattr(account, "permission_scope", None)
            if acct_id is None:
                continue
            if int(acct_id) == int(account_id):
                return None if scope is None else int(scope)
        return None

    def sync_account_combo(self, account_id: Optional[int]) -> None:
        w = self._window
        if not w._account_combo or account_id is None:
            return
        idx = w._account_combo.findData(int(account_id))
        if idx >= 0 and idx != w._account_combo.currentIndex():
            w._account_combo.blockSignals(True)
            w._account_combo.setCurrentIndex(idx)
            w._account_combo.blockSignals(False)

    @staticmethod
    def _account_label(account: object) -> str:
        account_id = getattr(account, "account_id", None)
        is_live = getattr(account, "is_live", None)
        trader_login = getattr(account, "trader_login", None)
        permission_scope = getattr(account, "permission_scope", None)
        if isinstance(account, dict):
            account_id = account.get("account_id")
            is_live = account.get("is_live")
            trader_login = account.get("trader_login")
            permission_scope = account.get("permission_scope")
        kind = "Live" if is_live is True else ("Demo" if is_live is False else "Account")
        label = f"{kind} {account_id}"
        if trader_login:
            label += f" · {trader_login}"
        if permission_scope == 0:
            label += " · VIEW"
        return label
