# ui/widgets/log_panel.py
from datetime import datetime
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit

class LogPanel(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()
        header = QHBoxLayout()
        title = QLabel("日誌面板")
        self._clear_button = QPushButton("清除")
        self._clear_button.clicked.connect(self.clear)
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        font.setPointSize(font.pointSize() + 2)
        self.text.setFont(font)

        header.addWidget(title)
        header.addStretch()
        header.addWidget(self._clear_button)

        layout.addLayout(header)
        layout.addWidget(self.text)
        self.setLayout(layout)

    def add_log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.text.append(f"[{ts}] {msg}")

    def clear(self) -> None:
        self.text.clear()
