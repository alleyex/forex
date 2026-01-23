from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QDateTime
from PySide6.QtWidgets import (
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QButtonGroup,
    QRadioButton,
    QFileDialog,
    QMessageBox,
    QWidget,
)

from ui.widgets.form_helpers import (
    apply_form_label_width,
    align_form_fields,
    build_browse_row,
    configure_form_layout,
)
from ui.styles.tokens import DIALOG_HINT, FORM_LABEL_WIDTH_WIDE, HISTORY_DIALOG

class HistoryDownloadDialog(QDialog):
    def __init__(self, symbol_id: int, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._symbol_id = symbol_id
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle("歷史資料下載")
        self.setMinimumWidth(680)
        self.setProperty("class", HISTORY_DIALOG)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        form_box = QGroupBox("資料設定")
        form_layout = QFormLayout(form_box)
        configure_form_layout(
            form_layout,
            horizontal_spacing=12,
            vertical_spacing=10,
            field_growth_policy=QFormLayout.AllNonFixedFieldsGrow,
        )
        apply_form_label_width(
            form_layout,
            FORM_LABEL_WIDTH_WIDE,
            alignment=Qt.AlignRight | Qt.AlignVCenter,
        )
        align_form_fields(form_layout, Qt.AlignLeft | Qt.AlignVCenter)

        self._range_group = QButtonGroup(self)
        range_row = QWidget()
        range_layout = QHBoxLayout(range_row)
        range_layout.setContentsMargins(0, 0, 0, 0)
        range_layout.setSpacing(8)
        for label in ["最近 1y", "最近 2y", "最近 3y"]:
            button = QRadioButton(label)
            self._range_group.addButton(button)
            range_layout.addWidget(button)
        self._range_group.buttonClicked.connect(self._apply_quick_range)
        form_layout.addRow("快速範圍", range_row)

        self._symbol_input = QComboBox()
        self._symbol_input.setEnabled(False)
        self._symbol_input.addItem("請先取得 symbol list", self._symbol_id)
        self._symbol_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        form_layout.addRow("貨幣種類", self._symbol_input)

        self._timeframe = QComboBox()
        self._timeframe.addItems(["M1", "M5", "M10", "M15", "H1"])
        index = self._timeframe.findText("M5")
        if index >= 0:
            self._timeframe.setCurrentIndex(index)
        self._timeframe.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        form_layout.addRow("資料類型", self._timeframe)

        utc_now = QDateTime.currentDateTimeUtc()
        self._start_time = QDateTimeEdit(utc_now.addYears(-3))
        self._start_time.setDisplayFormat("yyyy-MM-dd HH:mm")
        self._start_time.setTimeSpec(Qt.UTC)
        self._start_time.setCalendarPopup(True)
        self._start_time.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        form_layout.addRow("起始時間 (UTC)", self._start_time)

        self._end_time = QDateTimeEdit(utc_now)
        self._end_time.setDisplayFormat("yyyy-MM-dd HH:mm")
        self._end_time.setTimeSpec(Qt.UTC)
        self._end_time.setCalendarPopup(True)
        self._end_time.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        form_layout.addRow("結束時間 (UTC)", self._end_time)

        layout.addWidget(form_box)

        output_box = QGroupBox("輸出")
        output_layout = QFormLayout(output_box)
        configure_form_layout(
            output_layout,
            horizontal_spacing=12,
            vertical_spacing=10,
            field_growth_policy=QFormLayout.AllNonFixedFieldsGrow,
        )
        apply_form_label_width(
            output_layout,
            FORM_LABEL_WIDTH_WIDE,
            alignment=Qt.AlignRight | Qt.AlignVCenter,
        )
        align_form_fields(output_layout, Qt.AlignLeft | Qt.AlignVCenter)

        self._output_path = QLineEdit("data/raw_history/history.csv")
        self._output_path.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        output_row = build_browse_row(self._output_path, self._browse_path, spacing=8)
        output_layout.addRow("儲存檔案", output_row)

        self._info = QLabel("提示：請先載入 cTrader symbol list。")
        self._info.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._info.setProperty("class", DIALOG_HINT)
        output_layout.addRow(self._info)

        layout.addWidget(output_box)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("下載")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        layout.setAlignment(buttons, Qt.AlignRight)

        for button in self._range_group.buttons():
            if button.text().endswith("3y"):
                button.setChecked(True)
                break

    def _apply_quick_range(self) -> None:
        checked = self._range_group.checkedButton()
        if checked is None:
            return
        utc_now = QDateTime.currentDateTimeUtc()
        years = 1
        if checked.text().endswith("2y"):
            years = 2
        if checked.text().endswith("3y"):
            years = 3
        self._end_time.setDateTime(utc_now)
        self._start_time.setDateTime(utc_now.addYears(-years))

    def _browse_path(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "選擇儲存檔案", "history.csv", "CSV (*.csv)")
        if path:
            self._output_path.setText(path)

    def _validate(self) -> None:
        if not self._symbol_input.isEnabled():
            QMessageBox.warning(self, "缺少資料", "尚未取得 symbol list。")
            return
        if self._end_time.dateTime() <= self._start_time.dateTime():
            QMessageBox.warning(self, "時間錯誤", "結束時間必須大於起始時間。")
            return
        if not self._output_path.text().strip():
            QMessageBox.warning(self, "缺少路徑", "請選擇儲存位置。")
            return
        self.accept()

    def get_params(self) -> dict:
        start = self._start_time.dateTime().toSecsSinceEpoch() * 1000
        end = self._end_time.dateTime().toSecsSinceEpoch() * 1000
        return {
            "symbol_id": int(self._symbol_input.currentData() or self._symbol_id),
            "timeframe": self._timeframe.currentText(),
            "from_ts": int(start),
            "to_ts": int(end),
            "output_path": self._output_path.text().strip(),
            "start_text": self._start_time.dateTime().toString("yyyy-MM-dd HH:mm"),
            "end_text": self._end_time.dateTime().toString("yyyy-MM-dd HH:mm"),
        }

    def set_symbols(self, symbols: list) -> None:
        self._symbol_input.clear()
        if not symbols:
            self._symbol_input.addItem("無可用 symbol", self._symbol_id)
            self._symbol_input.setEnabled(False)
            return

        self._symbol_input.setEnabled(True)
        for symbol in symbols:
            if isinstance(symbol, dict):
                name = str(symbol.get("symbol_name") or symbol.get("name") or "")
                symbol_id = int(symbol.get("symbol_id") or symbol.get("symbolId") or 0)
            else:
                name = getattr(symbol, "name", None) or str(getattr(symbol, "symbol_name", ""))
                symbol_id = int(getattr(symbol, "symbol_id", 0))
            label = f"{name} ({symbol_id})" if name else str(symbol_id)
            self._symbol_input.addItem(label, symbol_id)

        index = self._symbol_input.findData(self._symbol_id)
        if index >= 0:
            self._symbol_input.setCurrentIndex(index)

    def set_timeframes(self, timeframes: list[str]) -> None:
        if not timeframes:
            return
        self._timeframe.clear()
        self._timeframe.addItems(timeframes)
        index = self._timeframe.findText("M5")
        if index >= 0:
            self._timeframe.setCurrentIndex(index)
