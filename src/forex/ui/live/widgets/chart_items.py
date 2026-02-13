from __future__ import annotations

from datetime import datetime

try:
    import pyqtgraph as pg
    from pyqtgraph.Qt import QtCore, QtGui
except Exception:  # pragma: no cover - optional dependency
    pg = None
    QtCore = None
    QtGui = None


if pg is not None:
    class TimeAxisItem(pg.AxisItem):
        def tickStrings(self, values, scale, spacing) -> list[str]:
            labels = []
            for value in values:
                try:
                    labels.append(datetime.utcfromtimestamp(value).strftime("%H:%M"))
                except (OSError, ValueError, OverflowError):
                    labels.append("")
            return labels


    class CandlestickItem(pg.GraphicsObject):
        def __init__(self, data: list[tuple[float, float, float, float, float]]):
            super().__init__()
            self._data = data
            self._picture = QtGui.QPicture()
            self._bounds = QtCore.QRectF(0.0, 0.0, 1.0, 1.0)
            self._generate_picture()

        def setData(self, data: list[tuple[float, float, float, float, float]]) -> None:
            self.prepareGeometryChange()
            self._data = data
            self._generate_picture()
            self.update()

        def _generate_picture(self) -> None:
            self._picture = QtGui.QPicture()
            painter = QtGui.QPainter(self._picture)
            if not self._data:
                self._bounds = QtCore.QRectF(0.0, 0.0, 1.0, 1.0)
                painter.end()
                return
            width = self._infer_half_width()
            times = [float(point[0]) for point in self._data]
            lows = [float(point[3]) for point in self._data]
            highs = [float(point[2]) for point in self._data]
            min_x = min(times) - width
            max_x = max(times) + width
            min_y = min(lows)
            max_y = max(highs)
            self._bounds = QtCore.QRectF(min_x, min_y, max(max_x - min_x, 1.0), max(max_y - min_y, 1e-8))
            for candle_ts, open_price, high, low, close in self._data:
                wick_pen = pg.mkPen("#9ca3af", width=1)
                painter.setPen(wick_pen)
                painter.drawLine(QtCore.QPointF(candle_ts, low), QtCore.QPointF(candle_ts, high))
                if open_price > close:
                    color = "#ef4444"
                    rect = QtCore.QRectF(candle_ts - width, close, width * 2, open_price - close)
                else:
                    color = "#10b981"
                    rect = QtCore.QRectF(candle_ts - width, open_price, width * 2, close - open_price)
                if rect.height() == 0:
                    painter.setPen(pg.mkPen(color, width=2))
                    painter.drawLine(
                        QtCore.QPointF(candle_ts - width, open_price),
                        QtCore.QPointF(candle_ts + width, open_price),
                    )
                else:
                    painter.setPen(pg.mkPen(color, width=2))
                    painter.setBrush(pg.mkBrush(color))
                    painter.drawRect(rect)
            painter.end()

        def _infer_half_width(self) -> float:
            if len(self._data) < 2:
                return 20.0
            times = [point[0] for point in self._data]
            diffs = [b - a for a, b in zip(times, times[1:]) if b > a]
            if not diffs:
                return 20.0
            diffs.sort()
            step = diffs[len(diffs) // 2]
            return max(1.0, step * 0.225)

        def paint(self, painter, *args) -> None:
            painter.drawPicture(0, 0, self._picture)

        def boundingRect(self) -> QtCore.QRectF:
            return QtCore.QRectF(self._bounds)

        def dataBounds(self, ax: int, _frac: float = 1.0, _orthoRange=None):
            if not self._data:
                return None
            if ax == 0:
                return [self._bounds.left(), self._bounds.right()]
            if ax == 1:
                return [self._bounds.top(), self._bounds.bottom()]
            return None
