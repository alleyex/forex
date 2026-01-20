# ui/widgets/trade_panel.py
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


class TradePanel(QWidget):
    trendbar_toggle_clicked = Signal()
    trendbar_history_clicked = Signal()
    basic_info_clicked = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QLabel("交易面板")
        title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.btn_basic_info = QPushButton("基本資料")
        self.btn_basic_info.setToolTip("取得帳戶基本資料")
        self.btn_trendbar_toggle = QPushButton("開始趨勢棒")
        self.btn_trendbar_toggle.setToolTip("開始或停止即時趨勢棒")
        self.btn_trendbar_history = QPushButton("M5 歷史(2年)")
        self.btn_trendbar_history.setToolTip("下載最近 2 年 M5 歷史資料")

        self.btn_basic_info.clicked.connect(self.basic_info_clicked.emit)
        self.btn_trendbar_toggle.clicked.connect(self.trendbar_toggle_clicked.emit)
        self.btn_trendbar_history.clicked.connect(self.trendbar_history_clicked.emit)

        layout.addWidget(title)
        layout.addWidget(self.btn_basic_info)
        layout.addWidget(self.btn_trendbar_toggle)
        layout.addWidget(self.btn_trendbar_history)
        layout.addStretch(1)

    def set_trendbar_active(self, active: bool) -> None:
        self.btn_trendbar_toggle.setText("停止趨勢棒" if active else "開始趨勢棒")
