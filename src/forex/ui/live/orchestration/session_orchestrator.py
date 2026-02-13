from __future__ import annotations

import time
from enum import Enum, auto

from forex.config.constants import ConnectionStatus
from forex.ui.shared.utils.formatters import format_connection_message


class LiveSessionPhase(Enum):
    DISCONNECTED = auto()
    CONNECTING = auto()
    APP_READY = auto()
    READY = auto()
    LOCKOUT = auto()


class LiveSessionOrchestrator:
    """Single-place runtime/session state transitions for live mode."""

    def __init__(self, window) -> None:
        self._window = window
        self._phase = LiveSessionPhase.DISCONNECTED
        self._last_resume_ts = 0.0
        self._last_data_activity_ts = 0.0
        self._last_stall_warn_ts = 0.0
        self._last_manual_toggle_ts = 0.0
        self._needs_runtime_rebuild = True
        self._last_oauth_retry_ts = 0.0

    @property
    def phase(self) -> LiveSessionPhase:
        return self._phase

    def _set_phase(self, phase: LiveSessionPhase, *, reason: str) -> None:
        if phase == self._phase:
            return
        previous = self._phase
        self._phase = phase
        self._window.logRequested.emit(
            f"ℹ️ session_phase | from={previous.name} | to={phase.name} | reason={reason}"
        )

    def broker_runtime_ready(self) -> bool:
        w = self._window
        if getattr(w, "_account_authorization_blocked", False):
            return False
        app_status = int(getattr(w._service, "status", 0) or 0)
        oauth_status = int(getattr(w._oauth_service, "status", 0) or 0)
        return (
            app_status >= int(ConnectionStatus.APP_AUTHENTICATED)
            and oauth_status >= int(ConnectionStatus.ACCOUNT_AUTHENTICATED)
        )

    def _derive_reconnect_phase(self) -> LiveSessionPhase:
        w = self._window
        app_status = int(getattr(w._service, "status", 0) or 0)
        oauth_status = int(getattr(w._oauth_service, "status", 0) or 0)

        if getattr(w, "_account_authorization_blocked", False):
            return LiveSessionPhase.LOCKOUT
        if app_status == int(ConnectionStatus.CONNECTING):
            return LiveSessionPhase.CONNECTING
        if app_status < int(ConnectionStatus.CONNECTED):
            return LiveSessionPhase.DISCONNECTED
        if app_status < int(ConnectionStatus.APP_AUTHENTICATED):
            return LiveSessionPhase.CONNECTING
        if oauth_status < int(ConnectionStatus.ACCOUNT_AUTHENTICATED):
            return LiveSessionPhase.APP_READY
        return LiveSessionPhase.READY

    def sync_reconnect_phase(self, *, reason: str = "status_refresh") -> LiveSessionPhase:
        phase = self._derive_reconnect_phase()
        self._set_phase(phase, reason=reason)
        return phase

    def suspend_runtime_loops(self) -> None:
        w = self._window
        w._auto_enabled = False
        w._chart_frozen = True
        w._pending_candles = None
        w._history_requested = False
        w._pending_history = False
        w._account_switch_in_progress = True
        w._stop_live_trendbar()
        w._stop_history_polling()
        w._stop_quote_subscription()
        self._needs_runtime_rebuild = True
        if w._funds_timer.isActive():
            w._funds_timer.stop()
        if w._auto_trade_toggle and w._auto_trade_toggle.isChecked():
            w._auto_trade_toggle.setChecked(False)

    def try_resume_runtime_loops(self, *, reason: str = "") -> None:
        w = self._window
        if not self.broker_runtime_ready():
            return
        if not w._app_state or not w._app_state.selected_account_id:
            return
        now = time.time()
        if now - self._last_resume_ts < 1.0:
            return
        self._last_resume_ts = now
        if self._needs_runtime_rebuild:
            self._rebuild_runtime_streams()
        w._request_recent_history()
        # Avoid hammering broker with both trendbar stream and periodic
        # history polling at the same time; use polling as fallback only.
        history_only_mode = bool(getattr(w, "_history_only_chart_mode", False))
        if history_only_mode or not bool(getattr(w, "_trendbar_active", False)):
            w._start_history_polling()
        else:
            w._stop_history_polling()
        w._ensure_quote_subscription()
        w._request_positions()
        w._refresh_account_balance()
        if not w._funds_timer.isActive():
            w._funds_timer.start()
        if reason:
            w.logRequested.emit(f"ℹ️ runtime_resume | reason={reason}")

    def _rebuild_runtime_streams(self) -> None:
        w = self._window
        # Recreate request/subscription services after reconnect to avoid
        # stale client bindings and stale in-flight flags.
        w._history_requested = False
        w._pending_history = False
        w._last_history_request_key = None
        w._last_history_success_key = None
        w._trendbar_active = False
        w._quote_subscribed_ids.clear()
        w._quote_subscribe_inflight.clear()
        w._dispose_history_service()
        w._dispose_trendbar_service()
        w._account_funds_uc = None
        # AppAuthService clears message handlers on disconnect; force local
        # handler refs to rebuild so quote/positions callbacks are re-bound.
        w._spot_message_handler = None
        w._positions_message_handler = None
        w._ensure_quote_handler()
        w._ensure_positions_handler()
        self._needs_runtime_rebuild = False
        w.logRequested.emit("ℹ️ runtime_rebuild | streams+handlers reset after reconnect")

    def mark_data_activity(self) -> None:
        self._last_data_activity_ts = time.time()

    def runtime_watchdog_tick(self) -> None:
        w = self._window
        if not self.broker_runtime_ready():
            return
        if not w._app_state or not w._app_state.selected_account_id:
            return
        now = time.time()
        if self._last_data_activity_ts <= 0:
            self._last_data_activity_ts = now
            return
        idle_seconds = now - self._last_data_activity_ts
        if idle_seconds < 20.0:
            return
        history_only_mode = bool(getattr(w, "_history_only_chart_mode", False))
        trendbar_active = bool(getattr(w, "_trendbar_active", False))
        # In stream mode, if trendbar is healthy, keep history polling off.
        if not history_only_mode and trendbar_active:
            w._stop_history_polling()
        if now - self._last_resume_ts < 15.0:
            return
        if now - self._last_stall_warn_ts >= 20.0:
            self._last_stall_warn_ts = now
            w.logRequested.emit(
                f"⚠️ runtime_stalled | idle={int(idle_seconds)}s | phase={self._phase.name}"
            )
        self.try_resume_runtime_loops(reason="watchdog_stalled_data_flow")

    def handle_toggle_connection(self, *, force: bool = False) -> None:
        w = self._window
        controller = getattr(w, "_connection_controller", None)
        if controller is None:
            w.logRequested.emit(format_connection_message("missing_use_cases"))
            return
        in_progress = bool(getattr(controller, "transition_in_progress", False))
        if in_progress:
            w.logRequested.emit(format_connection_message("in_progress"))
            return
        now = time.time()
        if not force and now - self._last_manual_toggle_ts < 1.0:
            w.logRequested.emit("⏳ Toggle ignored: connection transition in progress")
            return
        self._last_manual_toggle_ts = now
        app_auth = bool(getattr(controller, "is_app_authenticated", lambda: False)())
        oauth_auth = bool(getattr(controller, "is_oauth_authenticated", lambda: False)())
        if app_auth or oauth_auth:
            controller.disconnect_flow()
            return
        controller.connect_flow()

    def handle_app_auth_status(self, status: int) -> None:
        w = self._window
        if int(status) < int(ConnectionStatus.APP_AUTHENTICATED):
            oauth = w._oauth_service
            if oauth is not None and int(getattr(oauth, "status", 0) or 0) != int(ConnectionStatus.DISCONNECTED):
                try:
                    oauth.disconnect()
                except Exception:
                    pass
            w._oauth_label.setText("OAuth 狀態: ⏳ 等待 App 認證")
            self.suspend_runtime_loops()
            return

        if w._oauth_service:
            oauth_status = int(getattr(w._oauth_service, "status", 0) or 0)
            if oauth_status < int(ConnectionStatus.ACCOUNT_AUTHENTICATED):
                try:
                    w._oauth_service.connect()
                except Exception as exc:
                    w.logRequested.emit(f"⚠️ OAuth reconnect failed: {exc}")

    def handle_oauth_status(self, status: int) -> None:
        w = self._window
        if int(getattr(w._service, "status", 0) or 0) < int(ConnectionStatus.APP_AUTHENTICATED):
            w._account_switch_in_progress = True
            return

        if status >= ConnectionStatus.ACCOUNT_AUTHENTICATED:
            w._account_authorization_blocked = False
            last_auth_id = getattr(w._oauth_service, "last_authenticated_account_id", None)
            if last_auth_id is not None:
                w._last_authorized_account_id = int(last_auth_id)
            w._pending_full_reconnect = False
            if not w._accounts:
                w._refresh_accounts()
            if w._account_switch_in_progress and w._app_state and w._app_state.selected_account_id:
                token_account = getattr(getattr(w._oauth_service, "tokens", None), "account_id", None)
                if token_account and int(token_account) == int(w._app_state.selected_account_id):
                    w._account_switch_in_progress = False
            if w._app_state and w._app_state.selected_account_id:
                if last_auth_id is not None and int(w._app_state.selected_account_id) != int(last_auth_id):
                    w._account_switch_in_progress = True
                    w.logRequested.emit("⏳ Waiting for account authorization (account switch pending)")
                    w._schedule_full_reconnect()
                    return
            self._auto_enable_after_auth_ready()
            self.try_resume_runtime_loops(reason="oauth_authenticated")
            return

        self.suspend_runtime_loops()
        if getattr(w, "_account_authorization_blocked", False):
            return
        oauth_service = getattr(w, "_oauth_service", None)
        if oauth_service is None:
            return
        if int(status) == int(ConnectionStatus.DISCONNECTED):
            now = time.time()
            if now - self._last_oauth_retry_ts < 5.0:
                return
            self._last_oauth_retry_ts = now
            w.logRequested.emit("🔄 OAuth disconnected; retrying account auth...")
            try:
                oauth_service.connect()
            except Exception as exc:
                w.logRequested.emit(f"⚠️ OAuth auto-retry failed: {exc}")

    def _auto_enable_after_auth_ready(self) -> None:
        w = self._window
        toggle = getattr(w, "_auto_trade_toggle", None)
        if toggle is None:
            return
        if getattr(w, "_account_authorization_blocked", False):
            return
        app_state = getattr(w, "_app_state", None)
        if app_state is not None and getattr(app_state, "selected_account_scope", None) == 0:
            return
        try:
            if toggle.isChecked():
                return
            toggle.setChecked(True)
            w.logRequested.emit("ℹ️ Auto Trade enabled after auth ready")
        except Exception:
            pass

    def handle_app_state_changed(self, state) -> bool:
        """Returns True when fully handled by orchestrator."""
        w = self._window
        app_status = int(getattr(w._service, "status", 0) or 0)
        if app_status < ConnectionStatus.APP_AUTHENTICATED:
            w._account_switch_in_progress = True
            now = time.time()
            if now - float(getattr(w, "_last_oauth_not_ready_log_ts", 0.0)) >= 10.0:
                w._last_oauth_not_ready_log_ts = now
                w.logRequested.emit("⏳ AppState change ignored: App auth not authenticated yet")
            return True

        oauth_status = int(getattr(w._oauth_service, "status", 0) or 0)
        if oauth_status < ConnectionStatus.ACCOUNT_AUTHENTICATED:
            w._account_switch_in_progress = True
            now = time.time()
            if now - float(getattr(w, "_last_oauth_not_ready_log_ts", 0.0)) >= 10.0:
                w._last_oauth_not_ready_log_ts = now
                w.logRequested.emit("⏳ AppState change ignored: OAuth not authenticated yet")
            return True
        return False

    def handle_authenticated_app_state(self, state) -> None:
        """Handle account/scope updates after auth gates pass."""
        w = self._window
        if state.selected_account_id and w._oauth_service:
            last_auth_id = getattr(w._oauth_service, "last_authenticated_account_id", None)
            if last_auth_id is not None and int(last_auth_id) != int(state.selected_account_id):
                w._account_switch_in_progress = True
                w.logRequested.emit("⏳ Account changed; reconnecting to reauthorize")
                w._schedule_full_reconnect()
                return

        w._account_switch_in_progress = False
        w._sync_account_combo(state.selected_account_id)
        w._apply_trade_permission(state.selected_account_scope)
        if state.selected_account_id:
            self.try_resume_runtime_loops(reason="app_state_selected_account")
        else:
            w._stop_history_polling()

    def enter_authorization_lockout(self) -> bool:
        """Returns True when lockout entered; False when throttled/ignored."""
        w = self._window
        now = time.time()
        if w._account_authorization_blocked and now - w._last_auth_block_log_ts < 30.0:
            return False
        w._account_authorization_blocked = True
        w._last_auth_block_log_ts = now
        w._account_switch_in_progress = True

        w._history_requested = False
        w._pending_history = False
        w._last_history_request_key = None
        w._last_history_success_key = None
        w._trendbar_active = False
        w._quote_subscribed_ids.clear()
        w._quote_subscribe_inflight.clear()
        w._stop_history_polling()
        if w._funds_timer and w._funds_timer.isActive():
            w._funds_timer.stop()
        if w._auto_watchdog_timer and w._auto_watchdog_timer.isActive():
            w._auto_watchdog_timer.stop()
        if w._auto_enabled and w._auto_trade_toggle and w._auto_trade_toggle.isChecked():
            w._auto_trade_toggle.setChecked(False)
        w.logRequested.emit(
            "⛔ Authorization lockout: stopped funds/history/trendbar loops. "
            "Please switch to an authorized account and reconnect."
        )
        return True
