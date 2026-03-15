"""
Reusable status display widget
"""

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QLabel

from forex.config.constants import ConnectionStatus
from forex.ui.shared.utils.formatters import format_status_label


class StatusWidget(QLabel):
    """
    Status display widget.

    Shows the matching label and color for a `ConnectionStatus`.
    """

    # Default status mapping
    DEFAULT_STATUS_MAP: dict[ConnectionStatus, tuple[str, str]] = {
        ConnectionStatus.DISCONNECTED: ("Disconnected", "color: red"),
        ConnectionStatus.CONNECTING: ("Connecting...", "color: orange"),
        ConnectionStatus.CONNECTED: ("Connected", "color: blue"),
        ConnectionStatus.APP_AUTHENTICATED: ("App authenticated ✓", "color: green"),
        ConnectionStatus.ACCOUNT_AUTHENTICATED: ("Account authenticated ✓", "color: green"),
    }

    def __init__(
        self,
        parent=None,
        status_map: dict[ConnectionStatus, tuple[str, str]] | None = None,
    ):
        super().__init__(parent)
        self._status_map = status_map or self.DEFAULT_STATUS_MAP
        self.setAlignment(Qt.AlignCenter)
        self.update_status(ConnectionStatus.DISCONNECTED)

    @Slot(int)
    def update_status(self, status: int) -> None:
        """
        Update the displayed status.

        Args:
            status: Integer value of `ConnectionStatus`.
        """
        status_enum = ConnectionStatus(status) if isinstance(status, int) else status
        text, style = self._status_map.get(status_enum, ("Unknown", ""))
        self.setText(format_status_label(text))
        self.setStyleSheet(style)
