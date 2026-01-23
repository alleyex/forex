from __future__ import annotations

from typing import Callable, Optional, Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QPushButton,
    QLineEdit,
    QWidget,
)


def configure_form_layout(
    form: QFormLayout,
    *,
    label_alignment: Optional[Qt.AlignmentFlag] = None,
    form_alignment: Qt.AlignmentFlag = Qt.AlignTop,
    horizontal_spacing: int = 12,
    vertical_spacing: int = 10,
    margins: Sequence[int] = (0, 0, 0, 0),
    field_growth_policy: Optional[QFormLayout.FieldGrowthPolicy] = None,
) -> None:
    form.setLabelAlignment(label_alignment or (Qt.AlignRight | Qt.AlignVCenter))
    form.setFormAlignment(form_alignment)
    form.setHorizontalSpacing(horizontal_spacing)
    form.setVerticalSpacing(vertical_spacing)
    form.setContentsMargins(*margins)
    if field_growth_policy is not None:
        form.setFieldGrowthPolicy(field_growth_policy)


def apply_form_label_width(
    form: QFormLayout,
    width: int,
    *,
    alignment: Optional[Qt.AlignmentFlag] = None,
) -> None:
    for row in range(form.rowCount()):
        item = form.itemAt(row, QFormLayout.LabelRole)
        if not item:
            continue
        widget = item.widget()
        if widget is None:
            continue
        widget.setFixedWidth(width)
        if alignment is not None and hasattr(widget, "setAlignment"):
            widget.setAlignment(alignment)


def align_form_fields(form: QFormLayout, alignment: Qt.AlignmentFlag) -> None:
    for row in range(form.rowCount()):
        item = form.itemAt(row, QFormLayout.FieldRole)
        if not item:
            continue
        widget = item.widget()
        if widget is not None:
            if hasattr(widget, "setAlignment"):
                widget.setAlignment(alignment)
            form.setAlignment(widget, alignment)
            continue
        layout = item.layout()
        if layout is not None:
            form.setAlignment(layout, alignment)


def build_browse_row(
    line_edit: QLineEdit,
    on_clicked: Callable[[], None],
    button_text: str = "選擇",
    spacing: int = 6,
) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)

    button = QPushButton(button_text)
    button.clicked.connect(on_clicked)

    layout.addWidget(line_edit, stretch=1)
    layout.addWidget(button)
    return row
