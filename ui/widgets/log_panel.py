# ui/widgets/log_panel.py
from datetime import datetime
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit

class LogPanel(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        font.setPointSize(font.pointSize() + 2)
        self.text.setFont(font)
        layout.addWidget(self.text)
        self.setLayout(layout)

    def add_log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.text.append(f"[{ts}] {msg}")
        scrollbar = self.text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
