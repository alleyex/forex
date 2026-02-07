"""
帳戶選擇對話框
"""
from typing import List, Optional

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QLabel,
)

from forex.domain.accounts import Account


class AccountDialog(QDialog):
    """帳戶選擇對話框"""

    def __init__(self, accounts: List[Account], parent=None):
        super().__init__(parent)
        self._accounts = accounts
        self._selected: Optional[Account] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle("選擇帳戶")
        self.setMinimumSize(420, 280)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        layout.addWidget(QLabel("請選擇要操作的帳戶："))

        self._table = QTableWidget(self)
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["帳戶 ID", "環境", "交易登入", "權限"])
        self._table.setRowCount(len(self._accounts))
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QTableWidget.SingleSelection)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)

        for row, account in enumerate(self._accounts):
            self._table.setItem(row, 0, QTableWidgetItem(str(account.account_id)))
            env_text = "真實" if account.is_live else "模擬"
            self._table.setItem(row, 1, QTableWidgetItem(env_text))
            login_text = "" if account.trader_login is None else str(account.trader_login)
            self._table.setItem(row, 2, QTableWidgetItem(login_text))
            scope = account.permission_scope
            if scope == 1:
                scope_text = "可交易"
            elif scope == 0:
                scope_text = "僅檢視"
            else:
                scope_text = "未知"
            self._table.setItem(row, 3, QTableWidgetItem(scope_text))

        self._table.resizeColumnsToContents()
        if self._accounts:
            self._table.selectRow(0)

        layout.addWidget(self._table)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._btn_cancel = QPushButton("取消")
        self._btn_ok = QPushButton("確定")
        self._btn_ok.setDefault(True)

        self._btn_cancel.clicked.connect(self.reject)
        self._btn_ok.clicked.connect(self._accept_selection)

        btn_layout.addWidget(self._btn_cancel)
        btn_layout.addWidget(self._btn_ok)

        layout.addLayout(btn_layout)

    def _accept_selection(self) -> None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._accounts):
            self.reject()
            return
        self._selected = self._accounts[row]
        self.accept()

    def get_selected_account(self) -> Optional[Account]:
        return self._selected
