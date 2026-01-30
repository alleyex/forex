# ui_train/widgets/trade_panel.py
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


class TradePanel(QWidget):
    trendbar_toggle_requested = Signal()
    history_download_requested = Signal()
    account_info_requested = Signal()
    symbol_list_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QLabel("交易面板")
        title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.btn_account_info = QPushButton("基本資料")
        self.btn_account_info.setToolTip("取得帳戶基本資料")
        self.btn_trendbar_toggle = QPushButton("開始 K 線")
        self.btn_trendbar_toggle.setToolTip("開始或停止即時 K 線")
        self.btn_history_download = QPushButton("M5 歷史(2年)")
        self.btn_history_download.setToolTip("下載最近 2 年 M5 歷史資料")
        self.btn_symbol_list = QPushButton("Get Symbol List")
        self.btn_symbol_list.setToolTip("取得並保存 cTrader symbol list")

        self.btn_account_info.clicked.connect(self.account_info_requested.emit)
        self.btn_trendbar_toggle.clicked.connect(self.trendbar_toggle_requested.emit)
        self.btn_history_download.clicked.connect(self.history_download_requested.emit)
        self.btn_symbol_list.clicked.connect(self.symbol_list_requested.emit)

        layout.addWidget(title)
        layout.addWidget(self.btn_account_info)
        layout.addWidget(self.btn_trendbar_toggle)
        layout.addWidget(self.btn_history_download)
        layout.addWidget(self.btn_symbol_list)
        layout.addStretch(1)

    def set_trendbar_active(self, active: bool) -> None:
        self.btn_trendbar_toggle.setText("停止 K 線" if active else "開始 K 線")
