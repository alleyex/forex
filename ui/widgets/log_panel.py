# ui/widgets/log_panel.py
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QMenu, QToolButton, QWidget

from ui.widgets.log_widget import LogWidget


class LogPanel(LogWidget):
    hide_requested = Signal()
    maximize_requested = Signal(bool)

    def __init__(self):
        super().__init__(
            title="",
            with_timestamp=True,
            monospace=True,
            font_point_delta=2,
        )
        self._setup_header()

    def _setup_header(self) -> None:
        layout = self.layout()
        if layout is None:
            return
        header = QWidget(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(4, 4, 4, 4)
        header_layout.setSpacing(6)
        header_layout.addWidget(QWidget(header))
        header_layout.addStretch(1)
        self._hide_button = QToolButton(header)
        self._hide_button.setText("×")
        self._hide_button.setToolTip("隱藏日誌")
        self._hide_button.setAutoRaise(True)
        self._hide_button.clicked.connect(self.hide_requested.emit)
        header_layout.addWidget(self._hide_button)
        self._max_button = QToolButton(header)
        self._max_button.setCheckable(True)
        self._max_button.setText("▢")
        self._max_button.setToolTip("放大/還原")
        self._max_button.setAutoRaise(True)
        self._max_button.toggled.connect(self.maximize_requested.emit)
        header_layout.addWidget(self._max_button)
        self._more_button = QToolButton(header)
        self._more_button.setText("⋯")
        self._more_button.setToolTip("More")
        self._more_button.setAutoRaise(True)
        self._more_menu = QMenu(self._more_button)
        clear_action = self._more_menu.addAction("清除日誌")
        clear_action.triggered.connect(self._clear_logs)
        self._more_button.setMenu(self._more_menu)
        self._more_button.setPopupMode(QToolButton.InstantPopup)
        header_layout.addWidget(self._more_button)
        layout.insertWidget(0, header)


    def add_log(self, msg: str) -> None:
        self.append(msg)

    def set_collapsed(self, collapsed: bool) -> None:
        return

    def _clear_logs(self) -> None:
        self.clear_logs()

    def set_maximized(self, maximized: bool) -> None:
        if not hasattr(self, "_max_button"):
            return
        self._max_button.blockSignals(True)
        self._max_button.setChecked(maximized)
        self._max_button.blockSignals(False)
