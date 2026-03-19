from __future__ import annotations

import os
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from forex.application.broker.use_cases import BrokerUseCases
from forex.application.events import EventBus
from forex.application.state import AppState
from forex.infrastructure.broker.fake.provider import FakeProvider
from forex.ui.live.main_window import LiveMainWindow
from forex.ui.shared.widgets.log_widget import LogWidget
from forex.ui.train.main_window import MainWindow
from forex.ui.train.widgets.training_panel import TrainingPanel


class UISmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        QFont.insertSubstitution("Sans Serif", "Helvetica")
        cls._app.setFont(QFont("Helvetica", 10))

    def test_train_main_window_initializes_and_closes(self) -> None:
        window = MainWindow(
            use_cases=BrokerUseCases(FakeProvider()),
            event_bus=EventBus(),
            app_state=AppState(),
        )
        self.assertEqual(window.windowTitle(), "Forex Trading App")
        window.close()
        window.deleteLater()
        self._app.processEvents()

    def test_live_trade_history_refresh_uses_cooldown_unless_forced(self) -> None:
        class StubTradeHistoryService:
            def __init__(self) -> None:
                self.in_progress = False
                self.fetch_calls: list[tuple[int, int]] = []

            def set_callbacks(self, **_kwargs) -> None:
                return

            def clear_log_history(self) -> None:
                return

            def fetch(self, account_id: int, *, max_rows: int = 15) -> None:
                self.fetch_calls.append((account_id, max_rows))

        window = LiveMainWindow(
            use_cases=BrokerUseCases(FakeProvider()),
            event_bus=EventBus(),
            app_state=AppState(),
        )
        window._auto_connect_timer.stop()
        window._app_state.selected_account_id = 123
        window._trade_history_refresh_cooldown_s = 60.0
        window._trade_history_service = StubTradeHistoryService()
        window._service = object()
        window._is_broker_runtime_ready = lambda: True

        window._refresh_trade_history()
        window._refresh_trade_history()
        window._refresh_trade_history(force=True)

        self.assertEqual(
            window._trade_history_service.fetch_calls,
            [(123, 15), (123, 15)],
        )
        window.close()
        window.deleteLater()
        self._app.processEvents()

    def test_live_main_window_initializes_and_closes(self) -> None:
        window = LiveMainWindow(
            use_cases=BrokerUseCases(FakeProvider()),
            event_bus=EventBus(),
            app_state=AppState(),
        )
        # Keep smoke test deterministic: avoid deferred auto-connect side effects.
        window._auto_connect_timer.stop()
        self.assertIn("Live", window.windowTitle())
        self.assertEqual(window._project_root, Path(__file__).resolve().parents[1])
        self.assertTrue(
            (
                window._project_root / "config" / "training_presets" / "best_playback_s12.json"
            ).exists()
        )
        timeframes = [
            window._trade_timeframe.itemText(index)
            for index in range(window._trade_timeframe.count())
        ]
        self.assertIn("M10", timeframes)
        self.assertEqual(window._log_panel.current_filter, "INFO")
        self.assertEqual(window._lot_fixed.text(), "Fixed lot size")
        self.assertEqual(window._lot_risk.text(), "Risk % of balance")
        self.assertFalse(hasattr(window, "_risk_sizing_preview"))
        self.assertEqual(window._auto_margin_usage_cap_ratio, 0.5)
        self.assertEqual(window._auto_startup_warmup_bars, 1)
        self.assertTrue(window._weekend_guard.isChecked())
        self.assertEqual(window._weekend_cutoff_hour.value(), 20)
        self.assertEqual(window._weekend_resume_hour.value(), 0)
        self.assertIsNotNone(window._trade_history_table)
        self.assertEqual(window._trade_history_table.columnCount(), 4)
        self.assertEqual(window._quotes_table.parentWidget().minimumWidth(), 0)
        self.assertEqual(window._bottom_splitter.widget(1).title(), "Trade History")
        self.assertEqual(window._bottom_splitter.widget(2).title(), "Positions")
        window.close()
        window.deleteLater()
        self._app.processEvents()

    def test_live_trade_history_renders_nonzero_broker_rows(self) -> None:
        window = LiveMainWindow(
            use_cases=BrokerUseCases(FakeProvider()),
            event_bus=EventBus(),
            app_state=AppState(),
        )
        window._auto_connect_timer.stop()
        rows = [
            {
                "timestamp": 1773653100000,
                "symbol_id": 1,
                "side": "SELL",
                "volume": 800000,
                "realized_pnl": 12.34,
            }
        ]

        window._handle_trade_history_received(rows)

        self.assertEqual(window._trade_history_table.rowCount(), 1)
        self.assertEqual(window._trade_history_table.item(0, 1).text(), "EURUSD")
        self.assertEqual(window._trade_history_table.item(0, 2).text(), "SELL 0.080")
        self.assertEqual(window._trade_history_table.item(0, 3).text(), "+12.34")
        self.assertEqual(
            window._trade_history_table.item(0, 2).foreground().color().name(),
            "#ff7666",
        )
        self.assertEqual(
            window._trade_history_table.item(0, 2).background().color().name(),
            "#3f1f24",
        )
        self.assertEqual(
            window._trade_history_table.item(0, 3).foreground().color().name(),
            "#1fd19a",
        )
        self.assertEqual(
            window._trade_history_table.item(0, 3).background().color().name(),
            "#10392d",
        )
        window.close()
        window.deleteLater()
        self._app.processEvents()

    def test_live_trade_history_colors_negative_realized_pnl_red(self) -> None:
        window = LiveMainWindow(
            use_cases=BrokerUseCases(FakeProvider()),
            event_bus=EventBus(),
            app_state=AppState(),
        )
        window._auto_connect_timer.stop()
        rows = [
            {
                "timestamp": 1773653100000,
                "symbol_id": 1,
                "side": "BUY",
                "volume": 1000000,
                "realized_pnl": -8.5,
            }
        ]

        window._handle_trade_history_received(rows)

        self.assertEqual(window._trade_history_table.item(0, 2).text(), "BUY 0.100")
        self.assertEqual(window._trade_history_table.item(0, 3).text(), "-8.50")
        self.assertEqual(
            window._trade_history_table.item(0, 2).foreground().color().name(),
            "#1fd19a",
        )
        self.assertEqual(
            window._trade_history_table.item(0, 2).background().color().name(),
            "#10392d",
        )
        self.assertEqual(
            window._trade_history_table.item(0, 3).foreground().color().name(),
            "#ff7666",
        )
        self.assertEqual(
            window._trade_history_table.item(0, 3).background().color().name(),
            "#3f1f24",
        )
        window.close()
        window.deleteLater()
        self._app.processEvents()

    def test_live_trade_history_hides_zero_realized_pnl_rows(self) -> None:
        window = LiveMainWindow(
            use_cases=BrokerUseCases(FakeProvider()),
            event_bus=EventBus(),
            app_state=AppState(),
        )
        window._auto_connect_timer.stop()
        rows = [
            {
                "timestamp": 1773653100000,
                "symbol_id": 1,
                "side": "BUY",
                "volume": 1000000,
                "realized_pnl": 0.0,
            }
        ]

        window._handle_trade_history_received(rows)

        self.assertEqual(window._trade_history_table.rowCount(), 0)
        window.close()
        window.deleteLater()
        self._app.processEvents()

    def test_best_playback_compatibility_warnings_are_generated(self) -> None:
        warnings = LiveMainWindow._build_best_playback_compatibility_warnings(
            current_symbol="EURUSD",
            current_timeframe="M1",
            current_position_step=0.02,
            current_slippage_bps=0.03,
            applied_symbol="EURUSD",
            applied_timeframe="M10",
            env_config={"position_step": 0.05, "slippage_bps": 0.225},
            training_args={"reward_mode": "tp_sl_proxy"},
            metadata={"details": {"symbol_id": 1, "timeframe": "M10"}},
        )
        self.assertIn("timeframe changed from M1 to M10", warnings)
        self.assertIn("reward_mode is tp_sl_proxy, not path_penalty", warnings)
        self.assertIn("position_step was updated from 0.02 to 0.05", warnings)

    def test_training_panel_accepts_eval_mean_reward_metric(self) -> None:
        panel = TrainingPanel()
        panel.append_metric_point("eval/mean_reward", 10000, 0.25)
        self.assertEqual(list(panel._metric_data["eval/mean_reward"]["x"]), [10000])
        self.assertEqual(list(panel._metric_data["eval/mean_reward"]["y"]), [0.25])
        if panel._charts_available:
            x_data, y_data = panel._curves["eval/mean_reward"].getData()
            self.assertEqual(list(x_data), [10000])
            self.assertEqual(list(y_data), [0.25])
        panel.close()
        panel.deleteLater()
        self._app.processEvents()

    def test_log_widget_declares_explicit_foreground_color(self) -> None:
        widget = LogWidget()
        style_sheet = widget._text_edit.styleSheet()
        self.assertIn("color: #d8e0ea;", style_sheet)
        self.assertIn("selection-color: #f5f7fb;", style_sheet)
        widget.set_filter_level("WARN")
        self.assertEqual(widget.current_filter, "WARN")
        widget.close()
        widget.deleteLater()
        self._app.processEvents()

    def test_live_quote_table_declares_explicit_row_colors(self) -> None:
        window = LiveMainWindow(
            use_cases=BrokerUseCases(FakeProvider()),
            event_bus=EventBus(),
            app_state=AppState(),
        )
        window._auto_connect_timer.stop()
        style_sheet = window._quotes_table.styleSheet()
        self.assertIn("alternate-background-color: #252c35;", style_sheet)
        self.assertIn("selection-color: #f5f7fb;", style_sheet)
        self.assertIn("QTableWidget#quotesTable::item", style_sheet)
        self.assertEqual(window._quotes_table.verticalHeader().defaultSectionSize(), 30)
        self.assertEqual(window._quotes_table.horizontalHeader().height(), 34)
        window.close()
        window.deleteLater()
        self._app.processEvents()

    def test_live_status_bar_uses_named_shell_styles(self) -> None:
        window = LiveMainWindow(
            use_cases=BrokerUseCases(FakeProvider()),
            event_bus=EventBus(),
            app_state=AppState(),
        )
        window._auto_connect_timer.stop()
        self.assertEqual(window.statusBar().objectName(), "liveStatusBar")
        self.assertEqual(window._app_auth_label.objectName(), "statusChip")
        self.assertEqual(window._oauth_label.objectName(), "statusChip")
        window.close()
        window.deleteLater()
        self._app.processEvents()

    def test_log_widget_title_uses_dense_live_typography(self) -> None:
        widget = LogWidget(title="Runtime Log")
        style_sheet = widget._title_label.styleSheet()
        self.assertIn("font-size:12px", style_sheet)
        self.assertIn("font-weight:600", style_sheet)
        widget.close()
        widget.deleteLater()
        self._app.processEvents()


if __name__ == "__main__":
    unittest.main()
