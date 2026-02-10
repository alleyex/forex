from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from forex.application.broker.history_integrity import HistoryIntegrityReport, HistoryIntegrityService
from forex.ui.shared.widgets.layout_helpers import (
    align_form_fields,
    apply_form_label_width,
    build_browse_row,
    configure_form_layout,
)
from forex.ui.shared.styles.tokens import FORM_LABEL_WIDTH_WIDE


class HistoryIntegrityPanel(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._service = HistoryIntegrityService()
        self._report: Optional[HistoryIntegrityReport] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        file_box = QGroupBox("資料檢查")
        file_form = QFormLayout(file_box)
        configure_form_layout(
            file_form,
            label_alignment=Qt.AlignRight | Qt.AlignVCenter,
            field_growth_policy=QFormLayout.AllNonFixedFieldsGrow,
        )
        apply_form_label_width(file_form, FORM_LABEL_WIDTH_WIDE, alignment=Qt.AlignRight | Qt.AlignVCenter)
        align_form_fields(file_form, Qt.AlignLeft | Qt.AlignVCenter)

        self._csv_path = QLineEdit("data/raw_history/history.csv")
        self._csv_path.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        file_form.addRow("CSV 檔案", build_browse_row(self._csv_path, self._browse_csv))

        self._exclude_weekends = QCheckBox("排除週末缺口")
        self._exclude_weekends.setChecked(True)
        file_form.addRow("檢查設定", self._exclude_weekends)

        actions = QWidget()
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)
        self._run_button = QPushButton("開始檢查")
        self._run_button.clicked.connect(self._run_check)
        self._export_json_button = QPushButton("匯出報告(JSON)")
        self._export_json_button.setEnabled(False)
        self._export_json_button.clicked.connect(self._export_json)
        self._export_gaps_button = QPushButton("匯出缺口(CSV)")
        self._export_gaps_button.setEnabled(False)
        self._export_gaps_button.clicked.connect(self._export_gaps_csv)
        actions_layout.addWidget(self._run_button)
        actions_layout.addWidget(self._export_json_button)
        actions_layout.addWidget(self._export_gaps_button)
        actions_layout.addStretch(1)
        file_form.addRow("", actions)
        root.addWidget(file_box)

        summary_box = QGroupBox("摘要")
        summary_grid = QGridLayout(summary_box)
        summary_grid.setHorizontalSpacing(12)
        summary_grid.setVerticalSpacing(8)
        self._summary_labels: dict[str, QLabel] = {}
        rows = [
            ("Timeframe", "timeframe"),
            ("Rows", "rows"),
            ("Expected step (min)", "step"),
            ("Duplicates", "duplicates"),
            ("Backward order", "backward"),
            ("Gap events", "gaps"),
            ("Missing bars", "missing"),
        ]
        for idx, (label, key) in enumerate(rows):
            summary_grid.addWidget(QLabel(label), idx, 0)
            value = QLabel("-")
            value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            summary_grid.addWidget(value, idx, 1)
            self._summary_labels[key] = value
        root.addWidget(summary_box)

        gaps_box = QGroupBox("缺口明細")
        gaps_layout = QVBoxLayout(gaps_box)
        gaps_layout.setContentsMargins(8, 8, 8, 8)
        self._gaps_table = QTableWidget(0, 5)
        self._gaps_table.setHorizontalHeaderLabels(["起始(UTC)", "結束(UTC)", "差值(分鐘)", "缺少K數", "起訖分鐘"])
        self._gaps_table.horizontalHeader().setStretchLastSection(True)
        self._gaps_table.setEditTriggers(QTableWidget.NoEditTriggers)
        gaps_layout.addWidget(self._gaps_table)
        root.addWidget(gaps_box, stretch=1)

    def _browse_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "選擇歷史資料 CSV", self._csv_path.text(), "CSV (*.csv)")
        if path:
            self._csv_path.setText(path)

    def _run_check(self) -> None:
        path = self._csv_path.text().strip()
        if not path:
            QMessageBox.warning(self, "缺少檔案", "請先選擇 CSV 檔案。")
            return
        try:
            report = self._service.analyze(path, exclude_weekends=bool(self._exclude_weekends.isChecked()))
        except Exception as exc:
            QMessageBox.warning(self, "檢查失敗", str(exc))
            return
        self._report = report
        self._apply_report(report)
        self._export_json_button.setEnabled(True)
        self._export_gaps_button.setEnabled(True)

    def _apply_report(self, report: HistoryIntegrityReport) -> None:
        self._summary_labels["timeframe"].setText(report.timeframe)
        self._summary_labels["rows"].setText(str(report.row_count))
        self._summary_labels["step"].setText(str(report.expected_step_minutes))
        self._summary_labels["duplicates"].setText(str(report.duplicate_count))
        self._summary_labels["backward"].setText(str(report.backward_count))
        self._summary_labels["gaps"].setText(str(report.gap_count))
        self._summary_labels["missing"].setText(str(report.missing_bars))
        self._gaps_table.setRowCount(len(report.gaps))
        for row, gap in enumerate(report.gaps):
            values = [
                _fmt_utc_minutes(gap.start_utc_minutes),
                _fmt_utc_minutes(gap.end_utc_minutes),
                str(gap.diff_minutes),
                str(gap.missing_bars),
                f"{gap.start_utc_minutes} -> {gap.end_utc_minutes}",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignCenter)
                self._gaps_table.setItem(row, col, item)

    def _export_json(self) -> None:
        if not self._report:
            return
        default_name = Path(self._report.csv_path).with_suffix(".integrity.json").name
        path, _ = QFileDialog.getSaveFileName(self, "匯出檢查報告(JSON)", default_name, "JSON (*.json)")
        if not path:
            return
        try:
            self._service.export_json(self._report, path)
        except Exception as exc:
            QMessageBox.warning(self, "匯出失敗", str(exc))
            return
        QMessageBox.information(self, "完成", f"已匯出：{path}")

    def _export_gaps_csv(self) -> None:
        if not self._report:
            return
        default_name = Path(self._report.csv_path).with_suffix(".gaps.csv").name
        path, _ = QFileDialog.getSaveFileName(self, "匯出缺口清單(CSV)", default_name, "CSV (*.csv)")
        if not path:
            return
        try:
            self._service.export_gaps_csv(self._report, path)
        except Exception as exc:
            QMessageBox.warning(self, "匯出失敗", str(exc))
            return
        QMessageBox.information(self, "完成", f"已匯出：{path}")


def _fmt_utc_minutes(value: int) -> str:
    dt = datetime.fromtimestamp(value * 60, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M")
