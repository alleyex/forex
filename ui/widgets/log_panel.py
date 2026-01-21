# ui/widgets/log_panel.py
from ui.widgets.log_widget import LogWidget


class LogPanel(LogWidget):
    def __init__(self):
        super().__init__(
            title="",
            with_timestamp=True,
            monospace=True,
            font_point_delta=2,
        )

    def add_log(self, msg: str) -> None:
        self.append(msg)
