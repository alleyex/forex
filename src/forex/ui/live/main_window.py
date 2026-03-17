from __future__ import annotations

import json
import time
from pathlib import Path

from PySide6.QtCore import (
    QCoreApplication,
    QMetaObject,
    Qt,
    QThread,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGroupBox,
    QLabel,
    QMainWindow,
    QSplitter,
    QStyle,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

try:
    import pyqtgraph as pg
except Exception:  # pragma: no cover - optional dependency
    pg = None
else:
    try:
        pg.setConfigOptions(useOpenGL=False, antialias=False)
    except Exception:
        pass

from forex.application.broker.protocols import AppAuthServiceLike, OAuthServiceLike
from forex.application.broker.use_cases import BrokerUseCases
from forex.application.events import EventBus
from forex.application.state import AppState
from forex.config.constants import ConnectionStatus
from forex.config.paths import MODEL_DIR, SYMBOL_LIST_FILE, TOKEN_FILE
from forex.config.settings import OAuthTokens
from forex.ui.live.controllers.account_controller import LiveAccountController
from forex.ui.live.controllers.market_data_controller import LiveMarketDataController
from forex.ui.live.controllers.positions_controller import LivePositionsController
from forex.ui.live.controllers.quote_controller import LiveQuoteController
from forex.ui.live.controllers.symbol_controller import LiveSymbolController
from forex.ui.live.orchestration.autotrade_coordinator import LiveAutoTradeCoordinator
from forex.ui.live.orchestration.chart_coordinator import LiveChartCoordinator
from forex.ui.live.orchestration.layout_coordinator import LiveLayoutCoordinator
from forex.ui.live.orchestration.session_orchestrator import LiveSessionOrchestrator
from forex.ui.live.services.auto_lifecycle_service import LiveAutoLifecycleService
from forex.ui.live.services.auto_log_service import LiveAutoLogService
from forex.ui.live.services.auto_recovery_service import LiveAutoRecoveryService
from forex.ui.live.services.auto_runtime_service import LiveAutoRuntimeService
from forex.ui.live.services.auto_settings_persistence import LiveAutoSettingsPersistence
from forex.ui.live.services.auto_settings_validator import AutoTradeSettingsValidator
from forex.ui.live.services.value_formatter_service import LiveValueFormatterService
from forex.ui.live.state.window_state import initialize_live_window_state
from forex.ui.live.ui_builder import LiveUIBuilder
from forex.ui.live.widgets.chart_items import CandlestickItem, TimeAxisItem
from forex.ui.live.widgets.panel_factory import LivePanelFactory
from forex.ui.shared.controllers.connection_controller import ConnectionController
from forex.ui.shared.controllers.service_binding import clear_log_history_safe, set_callbacks_safe
from forex.ui.shared.utils.formatters import (
    format_app_auth_status,
    format_oauth_status,
)
from forex.ui.shared.widgets.log_widget import LogWidget


class LiveMainWindow(QMainWindow):
    """Live trading application window."""

    logRequested = Signal(str)
    appAuthStatusChanged = Signal(int)
    oauthStatusChanged = Signal(int)
    oauthError = Signal(str)
    oauthSuccess = Signal(object)
    appStateChanged = Signal(object)
    positionsUpdated = Signal(object)
    accountSummaryUpdated = Signal(object)
    historyReceived = Signal(list)
    tradeHistoryReceived = Signal(list)
    trendbarReceived = Signal(dict)
    quoteUpdated = Signal(int, object, object, object)
    _CARD_LINE_TITLE_COLOR = "#3a4452"
    _CARD_LINE_TITLE_FONT_SIZE_PX = 10
    _CARD_LINE_TITLE_OFFSET_PX = -20
    _BEST_PLAYBACK_PRESET_RELATIVE_PATH = Path("config/training_presets/best_playback_s12.json")

    # Initialization
    def __init__(
        self,
        *,
        use_cases: BrokerUseCases,
        event_bus: EventBus | None = None,
        app_state: AppState | None = None,
        service: AppAuthServiceLike | None = None,
        oauth_service: OAuthServiceLike | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._use_cases = use_cases
        self._event_bus = event_bus
        self._app_state = app_state
        self._service = service
        self._oauth_service = oauth_service
        self._symbol_controller = LiveSymbolController(self)
        initialize_live_window_state(self)
        self._account_controller = LiveAccountController(self)
        self._autotrade_coordinator = LiveAutoTradeCoordinator(self)
        self._chart_coordinator = LiveChartCoordinator(self)
        self._market_data_controller = LiveMarketDataController(self)
        self._quote_controller = LiveQuoteController(self)
        self._positions_controller = LivePositionsController(self)
        self._value_formatter = LiveValueFormatterService(self)
        self._layout_coordinator = LiveLayoutCoordinator(self)
        self._session_orchestrator = LiveSessionOrchestrator(self)
        self._auto_lifecycle_service = LiveAutoLifecycleService(self)
        self._auto_log_service = LiveAutoLogService(self)
        self._auto_recovery_service = LiveAutoRecoveryService(self)
        self._auto_runtime_service = LiveAutoRuntimeService(self)
        self._auto_settings_persistence = LiveAutoSettingsPersistence(self)
        self._auto_settings_validator = AutoTradeSettingsValidator(self)
        self._ui_builder = LiveUIBuilder(self)

        self._setup_ui()
        self._setup_autotrade_persistence()
        self._setup_connection_controller()
        self._connect_signals()
        self._auto_connect_timer.start(1000)

        if self._event_bus:
            self._event_bus.subscribe("log", self._log_panel.append)

        if self._service:
            self.set_service(self._service)
        if self._oauth_service:
            self.set_oauth_service(self._oauth_service)

        if self._app_state:
            self._app_state.subscribe(self.appStateChanged.emit)

        self._ensure_positions_handler()

    # Service Wiring
    def set_service(self, service: AppAuthServiceLike) -> None:
        if self._service and self._spot_message_handler:
            try:
                self._service.remove_message_handler(self._spot_message_handler)
            except Exception:
                pass
        self._service = service
        if (
            self._connection_controller
            and self._connection_controller.service is not service
        ):
            self._connection_controller.seed_services(service, self._oauth_service)
        clear_log_history_safe(self._service)
        set_callbacks_safe(
            self._service,
            on_log=self.logRequested.emit,
            on_status_changed=lambda s: self.appAuthStatusChanged.emit(int(s)),
        )
        if getattr(self._service, "status", None) is not None:
            self._app_auth_label.setText(
                format_app_auth_status(ConnectionStatus(self._service.status))
            )
        self._ensure_quote_handler()

    def set_oauth_service(self, service: OAuthServiceLike) -> None:
        self._oauth_service = service
        if (
            self._connection_controller
            and self._connection_controller.oauth_service is not service
        ):
            self._connection_controller.seed_services(self._service, service)
        clear_log_history_safe(self._oauth_service)
        set_callbacks_safe(
            self._oauth_service,
            on_log=self.logRequested.emit,
            on_error=lambda e: self.oauthError.emit(str(e)),
            on_oauth_success=lambda t: self.oauthSuccess.emit(t),
            on_status_changed=lambda s: self.oauthStatusChanged.emit(int(s)),
        )
        if getattr(self._oauth_service, "status", None) is not None:
            status = ConnectionStatus(self._oauth_service.status)
            self._oauth_label.setText(format_oauth_status(status))
            self._handle_oauth_status(int(status))

    # UI Construction
    def _setup_ui(self) -> None:
        self.setWindowTitle("Forex Trading App - Live")
        self.setMinimumSize(1280, 720)
        self.resize(1280, 720)

        self._log_panel = LogWidget(
            title="",
            with_timestamp=True,
            monospace=True,
            font_point_delta=2,
        )
        self._log_panel.set_filter_level("INFO")

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        chart_panel = self._build_chart_panel()
        autotrade_panel = self._build_autotrade_panel()
        top_splitter = QSplitter(Qt.Horizontal)
        top_splitter.addWidget(autotrade_panel)
        top_splitter.addWidget(chart_panel)
        top_splitter.setStretchFactor(0, 1)
        top_splitter.setStretchFactor(1, 2)
        self._top_splitter = top_splitter
        content_layout.addWidget(top_splitter, 1)

        quotes_panel = self._build_quotes_panel()
        positions_panel = self._build_positions_panel()
        trade_history_panel = self._build_trade_history_panel()
        bottom_splitter = QSplitter(Qt.Horizontal)
        bottom_splitter.addWidget(quotes_panel)
        bottom_splitter.addWidget(positions_panel)
        bottom_splitter.addWidget(trade_history_panel)
        bottom_splitter.addWidget(self._log_panel)
        bottom_splitter.setStretchFactor(0, 1)
        bottom_splitter.setStretchFactor(1, 2)
        bottom_splitter.setStretchFactor(2, 2)
        bottom_splitter.setStretchFactor(3, 1)
        self._bottom_splitter = bottom_splitter
        QTimer.singleShot(0, self._align_panels_at_startup)

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(content)
        splitter.addWidget(bottom_splitter)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        self._main_splitter = splitter
        QTimer.singleShot(0, self._init_main_splitter_sizes)

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(10, 10, 10, 10)
        central_layout.setSpacing(10)
        central_layout.addWidget(splitter)
        self.setCentralWidget(central)

        self._setup_toolbar()
        self._setup_status_bar()

    def _build_positions_panel(self) -> QWidget:
        return LivePanelFactory.build_positions_panel(self)

    def _build_trade_history_panel(self) -> QWidget:
        return LivePanelFactory.build_trade_history_panel(self)

    def _build_quotes_panel(self) -> QWidget:
        return LivePanelFactory.build_quotes_panel(self)

    def _build_autotrade_panel(self) -> QWidget:
        return self._ui_builder.build_autotrade_panel()

    # Layout Coordination
    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not getattr(self, "_panel_alignment_done", False):
            self._align_panels_at_startup()
        if getattr(self, "_main_splitter_done", False):
            self._apply_main_splitter_sizes()

    def _align_panels_at_startup(self) -> None:
        self._layout_coordinator.align_panels_at_startup()

    def _init_main_splitter_sizes(self) -> None:
        self._layout_coordinator.init_main_splitter_sizes()

    def _apply_main_splitter_sizes(self) -> None:
        self._layout_coordinator.apply_main_splitter_sizes()

    # Model Path Helpers
    def _browse_model_file(self) -> None:
        current_text = self._model_path.text().strip()
        current_path = self._resolve_model_path(current_text) if current_text else Path.cwd()
        start_path = current_path if current_path.exists() else current_path.parent
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select model file",
            str(start_path),
            "Model (*.zip);;All files (*)",
        )
        if path:
            self._model_path.setText(self._normalize_model_path_text(path))

    def _resolve_model_path(self, path_text: str) -> Path:
        raw = str(path_text).strip()
        if raw.startswith("models/"):
            suffix = raw[len("models/") :]
            return (Path(MODEL_DIR).expanduser().resolve() / suffix).resolve()
        path = Path(raw).expanduser()
        if path.is_absolute():
            return path
        return (Path.cwd() / path).resolve()

    def _normalize_model_path_text(self, path_text: str) -> str:
        raw = str(path_text).strip()
        if not raw:
            return ""
        if raw.startswith("models/"):
            return raw.replace("\\", "/")
        path = Path(raw).expanduser()
        if not path.is_absolute():
            return raw
        model_dir = Path(MODEL_DIR).expanduser().resolve()
        resolved = path.resolve()
        try:
            relative_model = resolved.relative_to(model_dir)
            return f"models/{relative_model.as_posix()}"
        except Exception:
            pass
        try:
            relative = resolved.relative_to(Path.cwd().resolve())
        except Exception:
            return str(path)
        return relative.as_posix()

    # Auto Trade Logging / Debug
    def _auto_log(self, message: str, *, level: str | None = None) -> None:
        self._auto_log_service.emit(message, level=level)

    def _auto_debug_enabled(self) -> bool:
        return bool(getattr(self, "_auto_debug", None) and self._auto_debug.isChecked())

    def _auto_debug_log(self, message: str) -> None:
        if not self._auto_debug_enabled():
            return
        self._auto_log(message, level="DEBUG")

    def _auto_debug_fields(self, event: str, **fields) -> None:
        lines = [str(event)]
        for key, value in fields.items():
            lines.append(f"  {key}={value}")
        payload = "\n".join(lines)
        if self._auto_debug_enabled():
            self._auto_log(payload, level="DEBUG")
            return
        panel = getattr(self, "_auto_log_panel", None)
        if panel is not None and hasattr(panel, "append"):
            panel.append(f"[DEBUG] {payload}")

    # Auto Trade Recovery / Polling
    def _auto_watchdog_tick(self) -> None:
        self._auto_recovery_service.auto_watchdog_tick()

    def _history_poll_tick(self) -> None:
        self._auto_recovery_service.history_poll_tick()

    def _start_history_polling(self) -> None:
        if (
            getattr(self, "_history_poll_timer", None)
            and not self._history_poll_timer.isActive()
        ):
            self._history_poll_timer.start()

    def _stop_history_polling(self) -> None:
        if (
            getattr(self, "_history_poll_timer", None)
            and self._history_poll_timer.isActive()
        ):
            self._history_poll_timer.stop()

    def _set_quote_chart_mode(self, enabled: bool) -> None:
        self._chart_coordinator.set_quote_chart_mode(enabled)

    # Auto Trade Lifecycle / Runtime
    def _toggle_auto_trade(self, enabled: bool) -> None:
        self._auto_lifecycle_service.toggle(enabled)

    def _load_auto_model(self) -> bool:
        return self._auto_runtime_service.load_auto_model()

    def _ensure_order_service(self) -> None:
        self._auto_runtime_service.ensure_order_service()

    def _handle_trade_timeframe_changed(self, timeframe: str) -> None:
        self._market_data_controller.set_trade_timeframe(timeframe)

    def _apply_best_playback_model_preset(self) -> None:
        payload = self._load_best_playback_preset()
        if payload is None:
            self._auto_log("❌ Best playback preset could not be loaded")
            return
        source_run = str(payload.get("source_run", "")).strip()
        if not source_run:
            self._auto_log("❌ Best playback preset is missing source_run")
            return
        run_dir = self._project_root / "data" / "training" / "runs" / source_run
        model_path = run_dir / "model.zip"
        if not model_path.exists():
            self._auto_log(f"❌ Best playback model not found: {model_path}")
            return
        training_args = self._load_json_file(run_dir / "training_args.json")
        env_config = self._load_json_file(run_dir / "model.env.json")
        metadata = self._load_training_data_metadata(training_args)
        current_symbol = self._trade_symbol.currentText().strip()
        current_timeframe = self._trade_timeframe.currentText().strip().upper()
        current_position_step = float(self._position_step.value())
        current_slippage_bps = float(self._slippage_bps.value())
        self._autotrade_loading = True
        try:
            self._model_path.setText(self._normalize_model_path_text(str(model_path)))
            self._apply_live_symbol(metadata)
            self._apply_live_timeframe(metadata)
            if isinstance(env_config, dict):
                if "position_step" in env_config:
                    self._position_step.setValue(float(env_config["position_step"]))
                if "slippage_bps" in env_config:
                    self._slippage_bps.setValue(float(env_config["slippage_bps"]))
        finally:
            self._autotrade_loading = False
        self._auto_settings_persistence.save()
        timeframe = self._trade_timeframe.currentText().strip()
        symbol = self._trade_symbol.currentText().strip()
        self._auto_log(
            "✅ Applied best playback model preset: "
            f"{model_path.name} | symbol={symbol or '-'} | timeframe={timeframe or '-'}"
        )
        warnings = self._build_best_playback_compatibility_warnings(
            current_symbol=current_symbol,
            current_timeframe=current_timeframe,
            current_position_step=current_position_step,
            current_slippage_bps=current_slippage_bps,
            applied_symbol=symbol,
            applied_timeframe=timeframe,
            env_config=env_config,
            training_args=training_args,
            metadata=metadata,
        )
        if warnings:
            self._auto_log("⚠️ Compatibility check:")
            for warning in warnings:
                self._auto_log(f"   - {warning}")
        else:
            self._auto_log("✅ Compatibility check passed for live preset application")

    def _apply_live_symbol(self, metadata: dict | None) -> None:
        if not isinstance(metadata, dict):
            return
        details = metadata.get("details", {})
        if not isinstance(details, dict):
            return
        symbol_id = details.get("symbol_id")
        try:
            symbol_id_int = int(symbol_id)
        except (TypeError, ValueError):
            return
        symbol_name = self._symbol_id_to_name.get(symbol_id_int, "").strip()
        if not symbol_name:
            return
        index = self._trade_symbol.findText(symbol_name)
        if index >= 0:
            self._trade_symbol.setCurrentIndex(index)

    def _apply_live_timeframe(self, metadata: dict | None) -> None:
        timeframe = ""
        if isinstance(metadata, dict):
            details = metadata.get("details", {})
            if isinstance(details, dict):
                timeframe = str(details.get("timeframe", "")).strip().upper()
        if not timeframe:
            return
        index = self._trade_timeframe.findText(timeframe)
        if index >= 0:
            self._trade_timeframe.setCurrentIndex(index)

    def _load_training_data_metadata(self, training_args: dict | None) -> dict | None:
        if not isinstance(training_args, dict):
            return None
        data_path_value = training_args.get("data") or training_args.get("data_path")
        data_path_text = str(data_path_value or "").strip()
        if not data_path_text:
            return None
        data_path = Path(data_path_text).expanduser()
        meta_path = Path(f"{data_path}.meta.json")
        return self._load_json_file(meta_path)

    def _load_best_playback_preset(self) -> dict | None:
        return self._load_json_file(
            self._project_root / self._BEST_PLAYBACK_PRESET_RELATIVE_PATH
        )

    @staticmethod
    def _load_json_file(path: Path) -> dict | None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _build_best_playback_compatibility_warnings(
        *,
        current_symbol: str,
        current_timeframe: str,
        current_position_step: float,
        current_slippage_bps: float,
        applied_symbol: str,
        applied_timeframe: str,
        env_config: dict | None,
        training_args: dict | None,
        metadata: dict | None,
    ) -> list[str]:
        warnings: list[str] = []
        details = metadata.get("details", {}) if isinstance(metadata, dict) else {}
        trained_symbol_id = details.get("symbol_id") if isinstance(details, dict) else None
        trained_timeframe = (
            str(details.get("timeframe", "")).strip().upper()
            if isinstance(details, dict)
            else ""
        )
        reward_mode = (
            str(training_args.get("reward_mode", "")).strip()
            if isinstance(training_args, dict)
            else ""
        )

        if current_symbol and applied_symbol and current_symbol != applied_symbol:
            warnings.append(f"symbol changed from {current_symbol} to {applied_symbol}")
        if current_timeframe and applied_timeframe and current_timeframe != applied_timeframe:
            warnings.append(
                f"timeframe changed from {current_timeframe} to {applied_timeframe}"
            )
        if applied_timeframe and trained_timeframe and applied_timeframe != trained_timeframe:
            warnings.append(
                "live timeframe "
                f"{applied_timeframe} differs from training timeframe {trained_timeframe}"
            )
        if trained_symbol_id is None:
            warnings.append("training data metadata did not include symbol_id")
        if not trained_timeframe:
            warnings.append("training data metadata did not include timeframe")
        if reward_mode and reward_mode != "path_penalty":
            warnings.append(f"reward_mode is {reward_mode}, not path_penalty")

        if isinstance(env_config, dict):
            model_position_step = env_config.get("position_step")
            model_slippage_bps = env_config.get("slippage_bps")
            if (
                model_position_step is not None
                and abs(float(model_position_step) - current_position_step) > 1e-9
            ):
                warnings.append(
                    "position_step was updated from "
                    f"{current_position_step:g} to {float(model_position_step):g}"
                )
            if (
                model_slippage_bps is not None
                and abs(float(model_slippage_bps) - current_slippage_bps) > 1e-9
            ):
                warnings.append(
                    "slippage_bps was updated from "
                    f"{current_slippage_bps:g} to {float(model_slippage_bps):g}"
                )
        else:
            warnings.append("model.env.json could not be loaded")

        return warnings

    # Auto Trade UI State / Persistence
    def _trading_widgets(self) -> list[QWidget]:
        return [
            self._auto_trade_toggle,
            self._trade_symbol,
            self._trade_timeframe,
            self._lot_fixed,
            self._lot_risk,
            self._lot_value,
            self._max_positions,
            self._stop_loss,
            self._take_profit,
            self._risk_guard,
            self._max_drawdown,
            self._daily_loss,
            self._min_signal_interval,
            self._slippage_bps,
            self._fee_bps,
            self._confidence,
            self._position_step,
            self._near_full_hold,
            self._same_side_rebalance,
            self._one_position_mode,
            self._scale_lot_by_signal,
            self._auto_debug,
            self._quote_affects_chart,
        ]

    def _apply_trade_permission(self, scope: int | None) -> None:
        trading_allowed = scope != 0
        for widget in self._trading_widgets():
            if widget:
                widget.setEnabled(trading_allowed)

        if self._autotrade_tabs:
            if getattr(self, "_basic_tab", None):
                basic_idx = self._autotrade_tabs.indexOf(self._basic_tab)
                if basic_idx >= 0:
                    self._autotrade_tabs.setTabEnabled(basic_idx, trading_allowed)
            if getattr(self, "_trade_tab", None):
                trade_idx = self._autotrade_tabs.indexOf(self._trade_tab)
                if trade_idx >= 0:
                    self._autotrade_tabs.setTabEnabled(trade_idx, trading_allowed)
            if getattr(self, "_advanced_tab", None):
                adv_idx = self._autotrade_tabs.indexOf(self._advanced_tab)
                if adv_idx >= 0:
                    self._autotrade_tabs.setTabEnabled(adv_idx, trading_allowed)

        if self._order_service:
            set_scope = getattr(self._order_service, "set_permission_scope", None)
            if callable(set_scope):
                set_scope(scope)

        if not trading_allowed:
            if self._auto_trade_toggle and self._auto_trade_toggle.isChecked():
                self._auto_trade_toggle.setChecked(False)
            self._auto_log("⚠️ Account permission is view-only. Trading has been disabled")
        self._history_requested = False
        self._pending_history = False
        self._last_history_request_key = None
        self._last_history_success_key = None
        self._stop_live_trendbar()
        if self._is_broker_runtime_ready():
            self._session_orchestrator.try_resume_runtime_loops(
                reason="trade_permission_updated"
            )

    def _sync_trade_symbol_choices(
        self,
        preferred_symbol: str | None = None,
    ) -> None:
        self._symbol_controller.sync_trade_symbol_choices(
            preferred_symbol=preferred_symbol
        )

    def _sync_lot_value_style(self) -> None:
        self._auto_settings_persistence.sync_lot_value_style()
        self._refresh_risk_sizing_preview()

    def _refresh_risk_sizing_preview(self) -> None:
        label = getattr(self, "_risk_sizing_preview", None)
        if label is None:
            return
        try:
            preview = self._autotrade_coordinator.estimate_lot_preview()
        except Exception:
            preview = {"mode": "fixed", "final_lot": 0.0, "cap_applied": False}
        if getattr(self, "_lot_risk", None) and self._lot_risk.isChecked():
            risk_lot = float(preview.get("risk_lot", preview.get("final_lot", 0.0)))
            final_lot = float(preview.get("final_lot", 0.0))
            stop_loss = float(preview.get("stop_loss_points", 0.0))
            balance = float(preview.get("balance", 0.0))
            used_margin = float(preview.get("used_margin", 0.0))
            max_used_margin = float(preview.get("max_used_margin", 0.0))
            if bool(preview.get("cap_applied", False)):
                label.setText(
                    f"Risk lot {risk_lot:.3f}, capped to {final_lot:.3f} "
                    f"to keep used margin <= {max_used_margin:.2f} "
                    f"(balance {balance:.2f}, used {used_margin:.2f}, SL {stop_loss:.0f})."
                )
            elif stop_loss > 0:
                label.setText(
                    f"Risk lot {final_lot:.3f} with balance {balance:.2f}, "
                    f"used margin {used_margin:.2f}/{max_used_margin:.2f}, "
                    f"SL {stop_loss:.0f}."
                )
            else:
                label.setText(f"Approx. {final_lot:.3f} lot. Add a stop loss for full risk sizing.")
            return
        label.setText(f"Fixed order size: {float(preview.get('final_lot', 0.0)):.3f} lot.")

    def _setup_autotrade_persistence(self) -> None:
        self._auto_settings_persistence.setup()

    # Auto Trade Hooks Used by Controllers/Services
    def _run_auto_trade_on_close(self) -> None:
        self._autotrade_coordinator.run_auto_trade_on_close()

    def _sync_auto_position_from_positions(self, positions: list[object]) -> None:
        self._autotrade_coordinator.sync_auto_position_from_positions(positions)

    def _refresh_account_balance(self) -> None:
        self._autotrade_coordinator.refresh_account_balance()

    def _refresh_trade_history(self) -> None:
        if not self._service or not self._app_state or not self._app_state.selected_account_id:
            return
        ready_fn = getattr(self, "_is_broker_runtime_ready", None)
        runtime_ready = bool(ready_fn()) if callable(ready_fn) else True
        if not runtime_ready or getattr(self, "_account_switch_in_progress", False):
            return
        try:
            if getattr(self, "_trade_history_service", None) is None:
                self._trade_history_service = self._use_cases.create_deal_history_service(
                    self._service
                )
            service = self._trade_history_service
            if getattr(service, "in_progress", False):
                return
        except Exception as exc:
            self.logRequested.emit(f"⚠️ Trade history service unavailable: {exc}")
            return

        def _on_deals(rows: list[dict]) -> None:
            self.tradeHistoryReceived.emit(rows)

        service.set_callbacks(
            on_deals_received=_on_deals,
            on_error=lambda error: self.logRequested.emit(f"❌ Trade history error: {error}"),
            on_log=self.logRequested.emit,
        )
        service.clear_log_history()
        service.fetch(int(self._app_state.selected_account_id), max_rows=15)

    # Quotes / Positions Controllers
    def _ensure_quote_handler(self) -> None:
        self._quote_controller.ensure_quote_handler()

    def _ensure_positions_handler(self) -> None:
        self._positions_controller.ensure_positions_handler()

    def _request_positions(self) -> None:
        self._positions_controller.request_positions()

    def _ensure_quote_subscription(self) -> None:
        self._quote_controller.ensure_quote_subscription()

    def _stop_quote_subscription(self) -> None:
        self._quote_controller.stop_quote_subscription()

    def _schedule_positions_refresh(self) -> None:
        self._positions_controller.schedule_positions_refresh()

    def _apply_positions_refresh(self) -> None:
        self._positions_controller.apply_positions_refresh()

    @staticmethod
    def _volume_to_lots(volume_value: float) -> float:
        return LivePositionsController.volume_to_lots(volume_value)

    def _current_price_text(
        self,
        *,
        symbol_id: int | None,
        side_value: int | None,
    ) -> str:
        return self._value_formatter.current_price_text(
            symbol_id=symbol_id,
            side_value=side_value,
        )

    def _format_spot_time(self, spot_ts) -> str:
        return self._value_formatter.format_spot_time(spot_ts)

    def _format_time(self, timestamp) -> str:
        return self._value_formatter.format_time(timestamp)

    def _append_trade_history_entry(
        self,
        *,
        symbol: str | None,
        event: str,
        side: str | None,
        lot_text: str | None,
        position_id=None,
        timestamp: str | None = None,
    ) -> None:
        table = getattr(self, "_trade_history_table", None)
        if table is None:
            return
        row = 0
        table.insertRow(row)
        values = [
            timestamp or time.strftime("%H:%M:%S"),
            symbol or "-",
            event or "-",
            side or "-",
            lot_text or "-",
            "-" if position_id in (None, "") else str(position_id),
        ]
        for col, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row, col, item)
        max_rows = int(getattr(self, "_trade_history_max_rows", 200))
        while table.rowCount() > max_rows:
            table.removeRow(table.rowCount() - 1)

    def _handle_trade_history_received(self, rows: list[dict]) -> None:
        table = getattr(self, "_trade_history_table", None)
        if table is None:
            return
        entries = list(rows or [])
        table.setRowCount(len(entries))
        for row, item in enumerate(entries):
            symbol_id = int(item.get("symbol_id", 0) or 0)
            symbol_name = self._symbol_id_to_name.get(symbol_id) or (
                f"#{symbol_id}" if symbol_id else "-"
            )
            volume = item.get("volume", 0)
            try:
                lot_text = f"{self._volume_to_lots(float(volume)):.3f}"
            except (TypeError, ValueError):
                lot_text = "-"
            timestamp = item.get("timestamp")
            time_text = self._format_time(timestamp) if timestamp else "-"
            values = [
                time_text,
                symbol_name,
                str(item.get("event", "-") or "-"),
                str(item.get("side", "-") or "-"),
                lot_text,
                str(item.get("position_id", "-") or "-"),
            ]
            for col, value in enumerate(values):
                existing = table.item(row, col)
                if existing is None:
                    existing = QTableWidgetItem(str(value))
                    existing.setTextAlignment(Qt.AlignCenter)
                    table.setItem(row, col, existing)
                else:
                    existing.setText(str(value))

    def _symbol_list_path(self) -> Path:
        return self._project_root / SYMBOL_LIST_FILE

    def _normalize_price(
        self,
        value,
        *,
        digits: int | None = None,
    ) -> float | None:
        return self._value_formatter.normalize_price(value, digits=digits)

    def _format_price(self, value, *, digits: int | None = None) -> str:
        return self._value_formatter.format_price(value, digits=digits)

    # Connection / Account Orchestration
    def _setup_toolbar(self) -> None:
        toolbar = QToolBar("Live toolbar", self)
        toolbar.setObjectName("liveToolbar")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.addToolBar(toolbar)

        connect_icon = self.style().standardIcon(QStyle.SP_BrowserReload)
        self._action_toggle_connection = QAction(connect_icon, "Connection", self)
        self._action_toggle_connection.setToolTip("Connect or disconnect from cTrader")
        toolbar.addAction(self._action_toggle_connection)
        self._action_toggle_connection.triggered.connect(self._toggle_connection)

    def _setup_status_bar(self) -> None:
        status_bar = self.statusBar()
        status_bar.setObjectName("liveStatusBar")
        self._app_auth_label = QLabel(format_app_auth_status(None))
        self._app_auth_label.setObjectName("statusChip")
        self._oauth_label = QLabel(format_oauth_status(None))
        self._oauth_label.setObjectName("statusChip")
        status_bar.addWidget(self._app_auth_label)
        status_bar.addWidget(self._oauth_label)

    def _is_broker_runtime_ready(self) -> bool:
        return self._session_orchestrator.broker_runtime_ready()

    def _update_reconnect_status(self, *, reason: str = "status_refresh") -> None:
        # Keep reconnect phase state machine updated, while reconnect text is hidden in UI.
        self._session_orchestrator.sync_reconnect_phase(reason=reason)

    def _setup_connection_controller(self) -> None:
        controller = ConnectionController(
            parent=self,
            use_cases=self._use_cases,
            app_state=self._app_state,
            event_bus=self._event_bus,
            on_service_ready=self.set_service,
            on_oauth_ready=self.set_oauth_service,
        )
        controller.seed_services(self._service, self._oauth_service)
        controller.logRequested.connect(self.logRequested.emit)
        controller.appAuthStatusChanged.connect(self.appAuthStatusChanged.emit)
        controller.oauthStatusChanged.connect(self.oauthStatusChanged.emit)
        self._connection_controller = controller

    def _connect_signals(self) -> None:
        self.logRequested.connect(self._on_log_requested)
        self.logRequested.connect(self._log_panel.append)
        self.appAuthStatusChanged.connect(self._handle_app_auth_status)
        self.oauthStatusChanged.connect(self._handle_oauth_status)
        self.oauthError.connect(self._handle_oauth_error)
        self.oauthSuccess.connect(self._handle_oauth_success)
        self.appStateChanged.connect(self._handle_app_state_changed)
        self.positionsUpdated.connect(self._positions_controller.apply_positions_update)
        self.accountSummaryUpdated.connect(self._handle_account_summary_updated)
        self.historyReceived.connect(self._handle_history_received)
        self.tradeHistoryReceived.connect(self._handle_trade_history_received)
        self.trendbarReceived.connect(self._handle_trendbar_received)
        self.quoteUpdated.connect(self._handle_quote_updated)

    @Slot(str)
    def _on_log_requested(self, _message: str) -> None:
        self._ui_diag_log_total += 1
        message = str(_message or "")
        if self._is_not_authorized_message(message):
            # During reconnect/auth handshake, broker may reject account-scoped
            # requests transiently. Avoid entering lockout until auth is settled.
            app_status = int(getattr(self._service, "status", 0) or 0)
            oauth_status = int(getattr(self._oauth_service, "status", 0) or 0)
            if (
                app_status < int(ConnectionStatus.APP_AUTHENTICATED)
                or oauth_status < int(ConnectionStatus.ACCOUNT_AUTHENTICATED)
            ):
                return
            now = time.time()
            # Throttle lockout trigger for bursts of identical broker errors.
            if now - float(getattr(self, "_last_auth_error_log_ts", 0.0)) >= 1.0:
                self._last_auth_error_log_ts = now
                self._enter_account_authorization_lockout()

    @Slot()
    def _toggle_connection(self) -> None:
        self._session_orchestrator.handle_toggle_connection()

    @Slot(int)
    def _handle_app_auth_status(self, status: int) -> None:
        self._app_auth_label.setText(format_app_auth_status(ConnectionStatus(status)))
        self._session_orchestrator.handle_app_auth_status(status)
        if self._oauth_service:
            oauth_status = int(getattr(self._oauth_service, "status", 0) or 0)
            if int(status) >= int(ConnectionStatus.APP_AUTHENTICATED):
                self._oauth_label.setText(format_oauth_status(ConnectionStatus(oauth_status)))
        self._update_reconnect_status(reason="app_auth_status_changed")

    @Slot(int)
    def _handle_oauth_status(self, status: int) -> None:
        self._oauth_label.setText(format_oauth_status(ConnectionStatus(status)))
        self.logRequested.emit(
            f"ℹ️ OAuth status -> {ConnectionStatus(status).name}"
        )
        self._session_orchestrator.handle_oauth_status(status)
        self._update_reconnect_status(reason="oauth_status_changed")

    def _handle_oauth_success(self, tokens: OAuthTokens) -> None:
        if tokens and tokens.account_id:
            self._last_authorized_account_id = int(tokens.account_id)
            self.logRequested.emit(f"✅ OAuth authorized account: {tokens.account_id}")

    def _handle_oauth_error(self, error: str) -> None:
        message = str(error)
        self.logRequested.emit(message)
        if "Trading account is not authorized" not in message:
            self._update_reconnect_status(reason="oauth_error")
            return
        token_account = getattr(
            getattr(self._oauth_service, "tokens", None),
            "account_id",
            None,
        )
        if token_account:
            try:
                self._unauthorized_accounts.add(int(token_account))
            except Exception:
                pass
        self._account_switch_in_progress = False
        self.logRequested.emit("⚠️ Selected account is not authorized for Open API.")
        self._enter_account_authorization_lockout()
        self._update_reconnect_status(reason="oauth_error_unauthorized")
        if (
            self._last_authorized_account_id
            and token_account
            and int(token_account) != int(self._last_authorized_account_id)
        ):
            self.logRequested.emit(
                "ℹ️ Account is not authorized. Switch to an available "
                "account and reconnect manually"
            )

    @staticmethod
    def _is_not_authorized_message(message: str) -> bool:
        lower = str(message or "").lower()
        return "trading account is not authorized" in lower

    def _enter_account_authorization_lockout(self) -> None:
        self._session_orchestrator.enter_authorization_lockout()
        self._update_reconnect_status(reason="authorization_lockout")

    def _load_tokens_for_accounts(self) -> OAuthTokens | None:
        try:
            return OAuthTokens.from_file(TOKEN_FILE)
        except Exception as exc:
            self.logRequested.emit(f"⚠️ Failed to read token file: {exc}")
            return None

    def _refresh_accounts(self) -> None:
        self._account_controller.refresh_accounts()

    def _handle_accounts_received(self, accounts: list[object]) -> None:
        self._account_controller.handle_accounts_received(accounts)

    def _handle_accounts_error(self, error: str) -> None:
        self._account_controller.handle_accounts_error(error)

    def _handle_account_combo_changed(self, index: int) -> None:
        self._account_controller.handle_account_combo_changed(index)

    def _sync_account_combo(self, account_id: int | None) -> None:
        self._account_controller.sync_account_combo(account_id)

    @Slot()
    def _schedule_full_reconnect(self) -> None:
        app = QApplication.instance()
        if app is not None and QThread.currentThread() != app.thread():
            QMetaObject.invokeMethod(
                self,
                "_schedule_full_reconnect",
                Qt.QueuedConnection,
            )
            return
        if self._pending_full_reconnect:
            return
        if not self._connection_controller:
            return
        self._pending_full_reconnect = True

        def _do_reconnect() -> None:
            self._pending_full_reconnect = False
            controller = self._connection_controller
            if not controller:
                return
            if getattr(controller, "transition_in_progress", False):
                self.logRequested.emit(
                    "⏳ Reconnect skipped: transition already in progress"
                )
                return
            self.logRequested.emit("🔁 Reconnecting to apply account switch")
            app_auth = bool(controller.is_app_authenticated())
            oauth_auth = bool(controller.is_oauth_authenticated())
            if app_auth or oauth_auth:
                controller.disconnect_flow()
                QTimer.singleShot(1200, self._connect_after_forced_disconnect)
            else:
                controller.connect_flow()

        QTimer.singleShot(500, _do_reconnect)

    @Slot()
    def _connect_after_forced_disconnect(self) -> None:
        controller = self._connection_controller
        if not controller:
            return
        if getattr(controller, "transition_in_progress", False):
            self.logRequested.emit(
                "⏳ Reconnect connect-phase skipped: transition already in progress"
            )
            return
        if controller.is_app_authenticated() or controller.is_oauth_authenticated():
            # Still authenticated; wait for next reconnect trigger rather than re-entering.
            return
        controller.connect_flow()

    def _handle_app_state_changed(self, state: AppState) -> None:
        if self._session_orchestrator.handle_app_state_changed(state):
            return
        self._session_orchestrator.handle_authenticated_app_state(state)

    # Market Data / Chart Runtime
    def _request_recent_history(self, *, force: bool = False) -> None:
        self._market_data_controller.request_recent_history(force=force)

    def _dispose_history_service(self) -> None:
        self._market_data_controller.dispose_history_service()

    def _dispose_trendbar_service(self) -> None:
        self._market_data_controller.dispose_trendbar_service()

    @Slot(object)
    def _handle_account_summary_updated(self, summary) -> None:
        self._session_orchestrator.mark_data_activity()
        self._positions_controller.apply_account_summary_update(summary)
        self._refresh_risk_sizing_preview()

    def _handle_history_received(self, rows: list[dict]) -> None:
        self._ui_diag_history_total += 1
        self._session_orchestrator.mark_data_activity()
        self._market_data_controller.handle_history_received(rows)

    def _start_live_trendbar(self) -> None:
        self._market_data_controller.start_live_trendbar()

    def _stop_live_trendbar(self) -> None:
        self._market_data_controller.stop_live_trendbar()

    def _handle_trendbar_received(self, data: dict) -> None:
        self._ui_diag_trendbar_total += 1
        self._session_orchestrator.mark_data_activity()
        self._market_data_controller.handle_trendbar_received(data)

    @Slot(int, object, object, object)
    def _handle_quote_updated(self, symbol_id: int, bid, ask, spot_ts) -> None:
        self._ui_diag_quote_total += 1
        self._session_orchestrator.mark_data_activity()
        self._quote_controller.handle_quote_updated(symbol_id, bid, ask, spot_ts)

    def _ui_heartbeat_tick(self) -> None:
        self._session_orchestrator.runtime_watchdog_tick()
        now = time.perf_counter()
        interval_s = 1.0
        if getattr(self, "_ui_heartbeat_timer", None):
            interval_s = max(0.1, float(self._ui_heartbeat_timer.interval()) / 1000.0)

        if self._ui_heartbeat_expected_ts <= 0:
            self._ui_heartbeat_expected_ts = now + interval_s
            self._ui_heartbeat_last_report_ts = now
            return

        lag_ms = max(0.0, (now - self._ui_heartbeat_expected_ts) * 1000.0)
        self._ui_heartbeat_expected_ts = now + interval_s
        if lag_ms > self._ui_heartbeat_max_lag_ms:
            self._ui_heartbeat_max_lag_ms = lag_ms

        qt_pending = False
        try:
            qt_pending = bool(QCoreApplication.hasPendingEvents())
        except Exception:
            qt_pending = False

        if qt_pending:
            self._ui_heartbeat_pending_streak += 1
        else:
            self._ui_heartbeat_pending_streak = 0

        queue_hint = 0
        queue_hint += int(self._pending_candles is not None)
        queue_hint += int(bool(self._history_requested))
        queue_hint += int(bool(self._positions_refresh_pending))
        queue_hint += len(getattr(self, "_quote_subscribe_inflight", set()) or set())
        queue_hint += int(qt_pending)

        if lag_ms >= 1500.0 and now - self._ui_heartbeat_last_warn_ts >= 30.0:
            self._ui_heartbeat_last_warn_ts = now
            self.logRequested.emit(
                "⚠️ UI heartbeat lag spike: "
                f"lag={lag_ms:.0f}ms queue_hint={queue_hint} "
                f"pending_streak={self._ui_heartbeat_pending_streak}"
            )

        elapsed = now - self._ui_heartbeat_last_report_ts
        if elapsed < 60.0:
            return

        logs_delta = self._ui_diag_log_total - self._ui_diag_last_log_total
        history_delta = self._ui_diag_history_total - self._ui_diag_last_history_total
        trendbar_delta = self._ui_diag_trendbar_total - self._ui_diag_last_trendbar_total
        quote_delta = self._ui_diag_quote_total - self._ui_diag_last_quote_total

        self._ui_diag_last_log_total = self._ui_diag_log_total
        self._ui_diag_last_history_total = self._ui_diag_history_total
        self._ui_diag_last_trendbar_total = self._ui_diag_trendbar_total
        self._ui_diag_last_quote_total = self._ui_diag_quote_total
        self._ui_heartbeat_last_report_ts = now

        logs_pm = (logs_delta / elapsed) * 60.0 if elapsed > 0 else 0.0
        history_pm = (history_delta / elapsed) * 60.0 if elapsed > 0 else 0.0
        trendbar_pm = (trendbar_delta / elapsed) * 60.0 if elapsed > 0 else 0.0
        quote_pm = (quote_delta / elapsed) * 60.0 if elapsed > 0 else 0.0

        log_entries = len(getattr(self._log_panel, "_entries", [])) if self._log_panel else 0
        auto_entries = (
            len(getattr(self._auto_log_panel, "_recent_raw", []))
            if self._auto_log_panel
            else 0
        )
        handler_count = 0
        service = getattr(self, "_service", None)
        if service is not None:
            getter = getattr(service, "message_handler_count", None)
            if callable(getter):
                try:
                    handler_count = int(getter())
                except Exception:
                    handler_count = 0

        self.logRequested.emit(
            "🫀 UI heartbeat: "
            f"lag_now={lag_ms:.0f}ms lag_max={self._ui_heartbeat_max_lag_ms:.0f}ms "
            f"queue_hint={queue_hint} pending_streak={self._ui_heartbeat_pending_streak} "
            f"log_rate={logs_pm:.0f}/min history_rate={history_pm:.1f}/min "
            f"trendbar_rate={trendbar_pm:.1f}/min quote_rate={quote_pm:.1f}/min "
            f"log_entries={log_entries} auto_entries={auto_entries} handlers={handler_count}"
        )
        self._ui_heartbeat_max_lag_ms = 0.0

    def _update_chart_from_quote(self, symbol_id: int, bid, ask, spot_ts) -> None:
        self._chart_coordinator.update_chart_from_quote(symbol_id, bid, ask, spot_ts)

    def _handle_chart_range_changed(self, *_args) -> None:
        self._chart_coordinator.handle_chart_range_changed(*_args)

    def _handle_chart_auto_button_clicked(self, *_args) -> None:
        self._chart_coordinator.handle_chart_auto_button_clicked(*_args)

    def _guard_chart_range(self) -> None:
        self._chart_coordinator.guard_chart_range()

    # Chart Construction / Updates
    def _build_chart_panel(self) -> QWidget:
        panel = QGroupBox("Live Candlestick Chart")
        layout = QVBoxLayout(panel)

        if pg is None:
            notice = QLabel(
                "PyQtGraph is not installed. Please install pyqtgraph to view the chart."
            )
            notice.setProperty("class", "placeholder")
            layout.addWidget(notice)
            return panel

        plot = pg.PlotWidget(axisItems={"bottom": TimeAxisItem(orientation="bottom")})
        plot.setBackground("#1f2328")
        plot.showGrid(x=True, y=True, alpha=0.15)
        plot.setLabel("bottom", "time")
        plot.setLabel("left", "price")
        plot.enableAutoRange(False, False)
        plot.setXRange(0, 1, padding=0)
        plot.setYRange(0, 1, padding=0)
        axis_pen = pg.mkPen("#5b6370")
        axis_text = pg.mkPen("#c9d1d9")
        plot.getAxis("bottom").setPen(axis_pen)
        plot.getAxis("bottom").setTextPen(axis_text)
        plot.getAxis("left").setPen(axis_pen)
        plot.getAxis("left").setTextPen(axis_text)
        try:
            plot_item = plot.getPlotItem()
            plot.getViewBox().sigRangeChangedFinished.connect(
                self._handle_chart_range_changed
            )
            auto_button = getattr(plot_item, "autoBtn", None)
            if auto_button is not None and hasattr(auto_button, "clicked"):
                # Override pyqtgraph default auto-range behavior: it can include
                # non-candle items and flatten the chart. We fully handle "A"
                # with our own candle-range normalization.
                try:
                    auto_button.clicked.disconnect(plot_item.autoBtnClicked)
                except Exception:
                    pass
                auto_button.clicked.connect(self._handle_chart_auto_button_clicked)
        except Exception:
            pass
        layout.addWidget(plot)

        self._candlestick_item = CandlestickItem([])
        plot.addItem(self._candlestick_item)
        self._last_price_line = pg.InfiniteLine(
            angle=0,
            pen=pg.mkPen("#9ca3af", width=1, style=Qt.DashLine),
            movable=False,
        )
        plot.addItem(self._last_price_line)
        # Anchor on the left so the text grows to the right and stays off candles.
        self._last_price_label = pg.TextItem(color="#e5e7eb", anchor=(0, 0.5))
        self._last_price_label.setZValue(10)
        plot.addItem(self._last_price_label)
        self._chart_plot = plot

        return panel

    def set_candles(self, candles: list[tuple[float, float, float, float, float]]) -> None:
        self._chart_coordinator.set_candles(candles)

    def _flush_chart_update(self) -> None:
        self._chart_coordinator.flush_chart_update()

    def _timeframe_minutes(self) -> int:
        return self._market_data_controller.timeframe_minutes()

    # Symbol Facade
    def _resolve_symbol_id(self, symbol_name: str) -> int:
        return self._symbol_controller.resolve_symbol_id(symbol_name)

    def _handle_trade_symbol_changed(self, symbol: str) -> None:
        self._symbol_controller.handle_trade_symbol_changed(symbol)

    def _fetch_symbol_details(self, symbol_name: str) -> None:
        self._symbol_controller.fetch_symbol_details(symbol_name)

    def _load_symbol_catalog(self) -> tuple[list[str], dict[str, int]]:
        return self._symbol_controller.load_symbol_catalog()

    def _filter_fx_symbols(self, names: list[str]) -> list[str]:
        return self._symbol_controller.filter_fx_symbols(names)

    def _default_quote_symbols(self) -> list[str]:
        return self._symbol_controller.default_quote_symbols()

    def _infer_quote_digits(self, symbol: str) -> int:
        return self._symbol_controller.infer_quote_digits(symbol)

    def _rebuild_quotes_table(self) -> None:
        self._symbol_controller.rebuild_quotes_table()
