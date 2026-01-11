# ui/widgets/trade_panel.py
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QPushButton, QVBoxLayout, QLabel

class TradePanel(QWidget):
    buy_clicked = Signal()
    sell_clicked = Signal()

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()

        title = QLabel("Trade Panel")
        self.btn_buy = QPushButton("BUY")
        self.btn_sell = QPushButton("SELL")

        self.btn_buy.clicked.connect(self.buy_clicked.emit)
        self.btn_sell.clicked.connect(self.sell_clicked.emit)

        layout.addWidget(title)
        layout.addWidget(self.btn_buy)
        layout.addWidget(self.btn_sell)
        layout.addStretch(1)

        self.setLayout(layout)
