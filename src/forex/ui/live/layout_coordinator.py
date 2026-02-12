from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QSplitter


class LiveLayoutCoordinator:
    """Coordinates splitter sizing/alignment for LiveMainWindow."""

    def __init__(self, window) -> None:
        self._window = window

    def init_splitter_sizes(self, splitter: QSplitter) -> None:
        w = self._window
        total = splitter.width()
        if total <= 0:
            return
        # Match the quotes panel width so the autotrade panel lines up.
        left = None
        bottom = getattr(w, "_bottom_splitter", None)
        if bottom is not None:
            sizes = bottom.sizes()
            if sizes:
                left = sizes[0]
        if left is None:
            left = max(220, int(total * 0.25))
        left = max(220, left)
        right = max(260, total - left)
        splitter.setSizes([left, right])

    def sync_field_widths(self) -> None:
        return

    def sync_top_splitter_sizes(self) -> None:
        w = self._window
        top = getattr(w, "_top_splitter", None)
        bottom = getattr(w, "_bottom_splitter", None)
        if top is None or bottom is None:
            return
        total = top.width()
        if total <= 0:
            return
        sizes = bottom.sizes()
        if not sizes:
            return
        left = min(max(220, sizes[0]), max(220, total - 220))
        right = total - left
        if right <= 0:
            return
        top.setSizes([left, right])

    def sync_bottom_splitter_sizes(self) -> None:
        w = self._window
        top = getattr(w, "_top_splitter", None)
        bottom = getattr(w, "_bottom_splitter", None)
        if top is None or bottom is None:
            return
        total = bottom.width()
        if total <= 0:
            return
        sizes = top.sizes()
        if not sizes:
            return
        left = min(max(220, sizes[0]), max(220, total - 320))
        mid = max(320, int(total * 0.50))
        right = total - left - mid
        if right < 200:
            right = 200
            mid = max(320, total - left - right)
        if left + mid + right <= total:
            bottom.setSizes([left, mid, right])

    def align_panels_at_startup(self) -> None:
        w = self._window
        if getattr(w, "_panel_alignment_done", False):
            return
        top = getattr(w, "_top_splitter", None)
        bottom = getattr(w, "_bottom_splitter", None)
        if top is None or bottom is None:
            return
        # First size bottom so quotes width is known, then align top to it.
        self.init_bottom_splitter_sizes(bottom)
        self.init_splitter_sizes(top)
        QTimer.singleShot(0, lambda: self.init_bottom_splitter_sizes(bottom))
        QTimer.singleShot(0, lambda: self.init_splitter_sizes(top))
        w._panel_alignment_done = True

    def init_main_splitter_sizes(self) -> None:
        w = self._window
        if getattr(w, "_main_splitter_done", False):
            return
        self.apply_main_splitter_sizes()
        w._main_splitter_done = True

    def bottom_preferred_height(self) -> int:
        w = self._window
        candidates: list[int] = []

        quotes_table = getattr(w, "_quotes_table", None)
        if quotes_table is not None:
            q_rows = max(1, quotes_table.rowCount())
            q_header = quotes_table.horizontalHeader().height()
            q_row_h = quotes_table.verticalHeader().defaultSectionSize()
            q_table_h = q_header + (q_rows * q_row_h) + quotes_table.frameWidth() * 2 + 8
            candidates.append(int(q_table_h + 80))

        positions_table = getattr(w, "_positions_table", None)
        if positions_table is not None:
            p_rows = max(2, positions_table.rowCount())
            p_header = positions_table.horizontalHeader().height()
            p_row_h = positions_table.verticalHeader().defaultSectionSize()
            p_table_h = p_header + (p_rows * p_row_h) + positions_table.frameWidth() * 2 + 8
            candidates.append(int(p_table_h + 160))

        log_panel = getattr(w, "_log_panel", None)
        if log_panel is not None:
            try:
                candidates.append(max(220, int(log_panel.sizeHint().height())))
            except Exception:
                candidates.append(220)

        for widget in (
            getattr(w, "_quotes_panel_widget", None),
            getattr(w, "_positions_panel_widget", None),
        ):
            if widget is None:
                continue
            try:
                candidates.append(max(int(widget.minimumSizeHint().height()), int(widget.sizeHint().height())))
            except Exception:
                continue
        if not candidates:
            return 280
        return max(260, max(candidates) + 12)

    def apply_main_splitter_sizes(self) -> None:
        w = self._window
        splitter = getattr(w, "_main_splitter", None)
        if splitter is None:
            return
        total = splitter.height()
        if total <= 0:
            return
        min_top = 180
        min_bottom = 220
        preferred_bottom = max(min_bottom, int(total * 0.30))
        max_bottom = max(min_bottom, total - min_top)
        bottom = min(preferred_bottom, max_bottom)
        top = total - bottom
        if top < min_top:
            top = min_top
            bottom = max(min_bottom, total - top)
        if top + bottom > total:
            bottom = max(min_bottom, total - top)
        if top > 0 and bottom > 0 and top + bottom <= total:
            splitter.setSizes([top, bottom])

    def init_bottom_splitter_sizes(self, splitter: QSplitter) -> None:
        total = splitter.width()
        if total <= 0:
            return
        quotes = max(220, int(total * 0.25))
        positions = max(420, int(total * 0.50))
        log = max(260, total - quotes - positions)
        if quotes + positions + log > total:
            log = max(200, total - quotes - positions)
        if quotes + positions + log <= total:
            splitter.setSizes([quotes, positions, log])

