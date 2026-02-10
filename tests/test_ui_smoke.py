from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont

from forex.application.broker.use_cases import BrokerUseCases
from forex.application.events import EventBus
from forex.application.state import AppState
from forex.infrastructure.broker.fake.provider import FakeProvider
from forex.ui.live.main_window import LiveMainWindow
from forex.ui.train.main_window import MainWindow


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
        self.assertEqual(window.windowTitle(), "外匯交易應用程式")
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
        window.close()
        window.deleteLater()
        self._app.processEvents()


if __name__ == "__main__":
    unittest.main()
