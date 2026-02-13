from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QLabel,
    QSizePolicy,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)


class LivePanelFactory:
    @staticmethod
    def build_positions_panel(window) -> QWidget:
        panel = QGroupBox("Positions")
        layout = QVBoxLayout(panel)

        account_combo = QComboBox()
        account_combo.setObjectName("accountSelector")
        account_combo.setMinimumWidth(220)
        account_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        account_combo.addItem("Select account", None)
        account_combo.currentIndexChanged.connect(window._handle_account_combo_changed)
        account_combo.setVisible(False)
        window._account_combo = account_combo

        summary = QFrame()
        summary.setObjectName("accountSummary")
        summary_layout = QGridLayout(summary)
        summary_layout.setContentsMargins(8, 6, 8, 6)
        summary_layout.setHorizontalSpacing(18)
        summary_layout.setVerticalSpacing(6)

        def _summary_item(title: str, key: str) -> QWidget:
            box = QWidget()
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(0, 0, 0, 0)
            box_layout.setSpacing(2)
            title_label = QLabel(title)
            title_label.setObjectName("summaryTitle")
            value_label = QLabel("-")
            value_label.setObjectName("summaryValue")
            box_layout.addWidget(title_label)
            box_layout.addWidget(value_label)
            window._account_summary_labels[key] = value_label
            return box

        summary_items = [
            ("Balance", "balance"),
            ("Equity", "equity"),
            ("Free Margin", "free_margin"),
            ("Used Margin", "used_margin"),
            ("Margin Level", "margin_level"),
            ("Net P/L", "net_pnl"),
            ("Currency", "currency"),
        ]
        row = 0
        col = 0
        for title, key in summary_items:
            summary_layout.addWidget(_summary_item(title, key), row, col)
            col += 1
            if col >= 4:
                row += 1
                col = 0

        summary.setStyleSheet(
            """
            QFrame#accountSummary {
                background: transparent;
                border: 1px solid rgba(255, 255, 255, 10);
                border-radius: 6px;
            }
            QLabel#summaryTitle {
                color: #9aa6b2;
                font-size: 11px;
            }
            QLabel#summaryValue {
                color: #e3e9ef;
                font-weight: 600;
            }
            """
        )
        layout.addWidget(summary)

        table = QTableWidget(0, 10)
        table.setObjectName("positionsTable")
        table.setHorizontalHeaderLabels(
            ["Symbol", "Side", "Volume", "Entry", "Current", "P/L", "SL", "TP", "Open Time", "Pos ID"]
        )
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setStyleSheet(
            """
            QTableWidget#positionsTable QScrollBar:vertical {
                background: transparent;
                width: 8px;
                margin: 2px;
            }
            QTableWidget#positionsTable QScrollBar::handle:vertical {
                background: rgba(210, 220, 232, 0.18);
                min-height: 24px;
                border-radius: 4px;
            }
            QTableWidget#positionsTable QScrollBar::handle:vertical:hover {
                background: rgba(210, 220, 232, 0.30);
            }
            QTableWidget#positionsTable QScrollBar::add-line:vertical,
            QTableWidget#positionsTable QScrollBar::sub-line:vertical,
            QTableWidget#positionsTable QScrollBar::add-page:vertical,
            QTableWidget#positionsTable QScrollBar::sub-page:vertical {
                background: transparent;
                height: 0px;
            }
            QTableWidget#positionsTable QScrollBar:horizontal {
                background: transparent;
                height: 8px;
                margin: 2px;
            }
            QTableWidget#positionsTable QScrollBar::handle:horizontal {
                background: rgba(210, 220, 232, 0.18);
                min-width: 24px;
                border-radius: 4px;
            }
            QTableWidget#positionsTable QScrollBar::handle:horizontal:hover {
                background: rgba(210, 220, 232, 0.30);
            }
            QTableWidget#positionsTable QScrollBar::add-line:horizontal,
            QTableWidget#positionsTable QScrollBar::sub-line:horizontal,
            QTableWidget#positionsTable QScrollBar::add-page:horizontal,
            QTableWidget#positionsTable QScrollBar::sub-page:horizontal {
                background: transparent;
                width: 0px;
            }
            """
        )

        layout.addWidget(table)
        window._positions_table = table
        return panel

    @staticmethod
    def build_quotes_panel(window) -> QWidget:
        panel = QGroupBox("Quotes")
        layout = QVBoxLayout(panel)

        rows = max(1, len(window._quote_symbols))
        table = QTableWidget(rows, 5)
        table.setObjectName("quotesTable")
        table.setHorizontalHeaderLabels(["Symbol", "Bid", "Ask", "Spread", "Time"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setStyleSheet(
            """
            QTableWidget#quotesTable QScrollBar:vertical {
                background: transparent;
                width: 8px;
                margin: 2px;
            }
            QTableWidget#quotesTable QScrollBar::handle:vertical {
                background: rgba(210, 220, 232, 0.18);
                min-height: 24px;
                border-radius: 4px;
            }
            QTableWidget#quotesTable QScrollBar::handle:vertical:hover {
                background: rgba(210, 220, 232, 0.30);
            }
            QTableWidget#quotesTable QScrollBar::add-line:vertical,
            QTableWidget#quotesTable QScrollBar::sub-line:vertical,
            QTableWidget#quotesTable QScrollBar::add-page:vertical,
            QTableWidget#quotesTable QScrollBar::sub-page:vertical {
                background: transparent;
                height: 0px;
            }
            QTableWidget#quotesTable QScrollBar:horizontal {
                background: transparent;
                height: 8px;
                margin: 2px;
            }
            QTableWidget#quotesTable QScrollBar::handle:horizontal {
                background: rgba(210, 220, 232, 0.18);
                min-width: 24px;
                border-radius: 4px;
            }
            QTableWidget#quotesTable QScrollBar::handle:horizontal:hover {
                background: rgba(210, 220, 232, 0.30);
            }
            QTableWidget#quotesTable QScrollBar::add-line:horizontal,
            QTableWidget#quotesTable QScrollBar::sub-line:horizontal,
            QTableWidget#quotesTable QScrollBar::add-page:horizontal,
            QTableWidget#quotesTable QScrollBar::sub-page:horizontal {
                background: transparent;
                width: 0px;
            }
            """
        )

        layout.addWidget(table)
        window._quotes_table = table
        window._rebuild_quotes_table()
        return panel
