# ui/widgets/trade_panel.py
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QPushButton, QVBoxLayout, QLabel

class TradePanel(QWidget):
    trendbar_toggle_clicked = Signal()
    trendbar_history_clicked = Signal()

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()

        title = QLabel("交易面板")
        self.btn_trendbar_toggle = QPushButton("開始趨勢棒")
        self.btn_trendbar_history = QPushButton("M5 歷史(2年)")

        self.btn_trendbar_toggle.clicked.connect(self.trendbar_toggle_clicked.emit)
        self.btn_trendbar_history.clicked.connect(self.trendbar_history_clicked.emit)

        layout.addWidget(title)
        layout.addWidget(self.btn_trendbar_toggle)
        layout.addWidget(self.btn_trendbar_history)
        layout.addStretch(1)

        self.setLayout(layout)

    def set_trendbar_active(self, active: bool) -> None:
        self.btn_trendbar_toggle.setText("停止趨勢棒" if active else "開始趨勢棒")
