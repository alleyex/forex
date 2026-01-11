# ui/widgets/log_panel.py
from datetime import datetime
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit

class LogPanel(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()
        title = QLabel("Log Panel")
        self.text = QTextEdit()
        self.text.setReadOnly(True)

        layout.addWidget(title)
        layout.addWidget(self.text)
        self.setLayout(layout)

    def add_log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.text.append(f"[{ts}] {msg}")
