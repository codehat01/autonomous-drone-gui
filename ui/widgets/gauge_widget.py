import math
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QFont
from utils.theme import COLORS


class GaugeWidget(QWidget):
    """Circular arc gauge. Arc sweeps 240 degrees from bottom-left to bottom-right."""

    START_ANGLE = 225   # degrees (Qt uses 1/16 degree units)
    SPAN_ANGLE  = 240

    def __init__(self, label: str, unit: str, min_val: float, max_val: float,
                 size: int = 120, parent=None):
        super().__init__(parent)
        self._label = label
        self._unit = unit
        self._min = min_val
        self._max = max_val
        self._value = min_val
        self.setFixedSize(size, size)

    def set_value(self, value: float) -> None:
        self._value = max(self._min, min(self._max, value))
        self.update()

    def _value_color(self) -> QColor:
        ratio = (self._value - self._min) / max(self._max - self._min, 1e-9)
        if ratio > 0.6:
            return QColor(COLORS['accent_green'])
        elif ratio > 0.3:
            return QColor(COLORS['accent_amber'])
        return QColor(COLORS['accent_red'])

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        margin = 10
        rect = QRectF(margin, margin, w - 2 * margin, h - 2 * margin)

        # Background arc
        pen = QPen(QColor(COLORS['border']))
        pen.setWidth(8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(rect,
                        int(self.START_ANGLE * 16),
                        -int(self.SPAN_ANGLE * 16))

        # Value arc
        ratio = (self._value - self._min) / max(self._max - self._min, 1e-9)
        span = int(ratio * self.SPAN_ANGLE * 16)
        pen.setColor(self._value_color())
        pen.setWidth(8)
        painter.setPen(pen)
        painter.drawArc(rect,
                        int(self.START_ANGLE * 16),
                        -span)

        # Center text: value
        painter.setPen(QColor(COLORS['text_primary']))
        font = QFont("Consolas", max(8, w // 8))
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter,
                         f"{self._value:.1f}{self._unit}")

        # Label below center
        label_rect = QRectF(0, h * 0.65, w, h * 0.25)
        font2 = QFont("Segoe UI", max(6, w // 14))
        painter.setFont(font2)
        painter.setPen(QColor(COLORS['text_secondary']))
        painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, self._label)
