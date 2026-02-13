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
