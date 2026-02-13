from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re

from PySide6.QtCore import Qt, Signal, Slot, QThread
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QGridLayout,
    QVBoxLayout,
    QWidget,
)

from forex.ui.shared.utils.formatters import format_timestamped_message


@dataclass
class _DecisionEntry:
    timestamp: str
    level: str
    event: str
    fields: dict[str, str]
    raw: str


class DecisionInspectorWidget(QWidget):
    appendRequested = Signal(str)

    _LEVEL_PREFIX_PATTERN = re.compile(r"^\[(DEBUG|INFO|OK|WARN|ERROR|TRADING|TRADE)\]\s*", re.IGNORECASE)
    _TIMESTAMP_PREFIX_PATTERN = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\]\s*")

    _INPUT_FIELDS = [
        ("decision_time", "Time"),
        ("tf", "Timeframe"),
        ("candles", "Candles"),
        ("features", "Features"),
        ("pos", "Position"),
        ("action", "Action"),
        ("target", "Target"),
        ("confidence", "Confidence"),
    ]
    _NORMALIZED_FIELDS = [
        ("threshold", "Threshold"),
        ("target", "Target"),
        ("desired_raw", "Desired Raw"),
        ("desired", "Desired"),
        ("step", "Step"),
        ("pos", "Position"),
        ("pos_id", "Pos ID"),
    ]
    _STATE_FIELDS = [
        ("symbol", "Symbol"),
        ("side", "Side"),
        ("desired", "Desired"),
        ("open_same", "Open Same"),
        ("open_symbol", "Open Symbol"),
        ("cap", "Cap"),
        ("near_full_hold", "Near-Full Hold"),
        ("rebalance", "Rebalance"),
    ]

    def __init__(
        self,
        title: str = "Auto Trade",
        parent=None,
        *,
        with_timestamp: bool = True,
        max_entries: int = 200,
    ) -> None:
        super().__init__(parent)
        self._with_timestamp = with_timestamp
        self._max_entries = max(20, int(max_entries))
        self._recent_raw: list[str] = []
        self._latest_cycle_time = "--:--:--"
        self._latest_input: _DecisionEntry | None = None
        self._latest_normalized: _DecisionEntry | None = None
        self._latest_state: _DecisionEntry | None = None
        self._input_labels: dict[str, QLabel] = {}
        self._normalized_labels: dict[str, QLabel] = {}
        self._state_labels: dict[str, QLabel] = {}
        self._setup_ui(title)
        self.appendRequested.connect(self._append_on_ui_thread, Qt.QueuedConnection)
        self._render()

    def _setup_ui(self, title: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        _ = title

        layout.addWidget(self._build_stage_card("Decision Input", self._INPUT_FIELDS, self._input_labels))
        layout.addWidget(self._build_stage_card("Decision Normalized", self._NORMALIZED_FIELDS, self._normalized_labels))
        layout.addWidget(self._build_stage_card("Strategy State", self._STATE_FIELDS, self._state_labels))

    def _build_stage_card(
        self,
        title: str,
        fields: list[tuple[str, str]],
        target_labels: dict[str, QLabel],
    ) -> QGroupBox:
        box = QGroupBox(title)
        box.setObjectName("card")
        box.setProperty("titleTone", "line")
        box.setProperty("titleAlign", "left")
        grid = QGridLayout(box)
        grid.setContentsMargins(12, 12, 12, 12)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)

        for index, (field, label_text) in enumerate(fields):
            row = index // 2
            col = index % 2
            cell = QWidget(box)
            cell_layout = QHBoxLayout(cell)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.setSpacing(4)

            shown_label = label_text
            if field == "decision_time":
                shown_label = self._time_label_with_local_offset()

            key_label = QLabel(f"{shown_label}:", cell)
            key_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            key_label.setStyleSheet("color:#9aa6b2; font-weight:500;")

            value_label = QLabel("-", cell)
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            value_label.setStyleSheet("color:#d3d8e0; font-weight:600;")

            cell_layout.addWidget(key_label)
            cell_layout.addWidget(value_label, 1)
            grid.addWidget(cell, row, col)
            target_labels[field] = value_label

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        return box

    @staticmethod
    def _time_label_with_local_offset() -> str:
        now = datetime.now().astimezone()
        offset = now.utcoffset()
        if offset is None:
            return "Time (±H)"
        hours_value = offset.total_seconds() / 3600.0
        rounded = round(hours_value)
        if abs(hours_value - rounded) < 1e-9:
            offset_text = f"{int(rounded):+d}"
        else:
            offset_text = f"{hours_value:+.2f}".rstrip("0").rstrip(".")
        return f"Time ({offset_text})"

    @Slot(str)
    def append(self, message: str) -> None:
        if QThread.currentThread() is not self.thread():
            self.appendRequested.emit(message)
            return
        self._append_on_ui_thread(message)

    @Slot(str)
    def _append_on_ui_thread(self, message: str) -> None:
        text = str(message or "").strip()
        if not text:
            return

        timestamp = datetime.now().strftime("%H:%M:%S") if self._with_timestamp else ""
        input_ts, no_ts = self._strip_timestamp(text)
        if input_ts:
            timestamp = input_ts
        level, body = self._split_level(no_ts)
        event, fields = self._parse_body(body)
        raw = format_timestamped_message(f"[{level}] {body}", timestamp) if timestamp else f"[{level}] {body}"

        self._recent_raw.append(raw)
        if len(self._recent_raw) > self._max_entries:
            self._recent_raw = self._recent_raw[-self._max_entries :]

        if level == "DEBUG" and event == "decision_input":
            self._latest_cycle_time = timestamp or self._latest_cycle_time
            self._latest_input = _DecisionEntry(
                timestamp=timestamp,
                level=level,
                event=event,
                fields=fields,
                raw=raw,
            )
            self._render()
            return

        if level == "DEBUG" and event == "decision_normalized":
            self._latest_cycle_time = timestamp or self._latest_cycle_time
            self._latest_normalized = _DecisionEntry(
                timestamp=timestamp,
                level=level,
                event=event,
                fields=fields,
                raw=raw,
            )
            self._render()
            return

        if level == "DEBUG" and event == "strategy_state":
            self._latest_cycle_time = timestamp or self._latest_cycle_time
            self._latest_state = _DecisionEntry(
                timestamp=timestamp,
                level=level,
                event=event,
                fields=fields,
                raw=raw,
            )
            self._render()

    def _render(self) -> None:
        for field, _label in self._INPUT_FIELDS:
            self._input_labels[field].setText("-")
        for field, _label in self._NORMALIZED_FIELDS:
            self._normalized_labels[field].setText("-")
        for field, _label in self._STATE_FIELDS:
            self._state_labels[field].setText("-")
        self._input_labels["decision_time"].setText(self._latest_cycle_time)

        if self._latest_input:
            for field, _label in self._INPUT_FIELDS:
                if field in self._latest_input.fields:
                    value = self._display_value(self._latest_input.fields[field])
                    self._input_labels[field].setText(value)

        if self._latest_normalized:
            for field, _label in self._NORMALIZED_FIELDS:
                if field in self._latest_normalized.fields:
                    value = self._display_value(self._latest_normalized.fields[field])
                    self._normalized_labels[field].setText(value)

        if self._latest_state:
            for field, _label in self._STATE_FIELDS:
                if field in self._latest_state.fields:
                    value = self._display_value(self._latest_state.fields[field])
                    self._state_labels[field].setText(value)

    @staticmethod
    def _display_value(raw_value: str) -> str:
        text = str(raw_value).strip()
        if not text:
            return text
        numeric_like = any(ch in text for ch in (".", "e", "E"))
        if not numeric_like:
            return text
        try:
            value = float(text)
        except (TypeError, ValueError):
            return text
        return f"{value:.2f}"

    @staticmethod
    def _strip_timestamp(text: str) -> tuple[str, str]:
        payload = str(text).lstrip()
        match = DecisionInspectorWidget._TIMESTAMP_PREFIX_PATTERN.match(payload)
        if not match:
            return "", payload
        return match.group(1), payload[match.end() :].lstrip()

    @staticmethod
    def _split_level(text: str) -> tuple[str, str]:
        payload = str(text).lstrip()
        level_match = DecisionInspectorWidget._LEVEL_PREFIX_PATTERN.match(payload)
        if not level_match:
            return "INFO", payload
        level = level_match.group(1).upper()
        if level in {"TRADING", "TRADE"}:
            level = "INFO"
        return level, payload[level_match.end() :].lstrip()

    @staticmethod
    def _parse_body(body: str) -> tuple[str, dict[str, str]]:
        if "\n" in body:
            lines = [line.strip() for line in body.splitlines() if line.strip()]
            event = lines[0] if lines else "message"
            fields: dict[str, str] = {}
            for line in lines[1:]:
                if "=" in line:
                    key, value = line.split("=", 1)
                    fields[key.strip()] = value.strip()
            return event, fields

        if "|" in body:
            parts = [part.strip() for part in body.split("|") if part.strip()]
            event = parts[0] if parts else "message"
            fields = {}
            for part in parts[1:]:
                if "=" in part:
                    key, value = part.split("=", 1)
                    fields[key.strip()] = value.strip()
            return event, fields

        tokens = body.split()
        if not tokens:
            return "message", {}
        event = tokens[0]
        fields = {}
        for token in tokens[1:]:
            if "=" in token:
                key, value = token.split("=", 1)
                fields[key.strip()] = value.strip()
        return event, fields

    def clear_logs(self) -> None:
        self._recent_raw.clear()
        self._latest_cycle_time = "--:--:--"
        self._latest_input = None
        self._latest_normalized = None
        self._latest_state = None
        self._render()

    # Top title and copy/clear buttons removed by design.
