import math
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QPolygonF, QFont
from utils.theme import COLORS


class CompassWidget(QWidget):
    """Rotating compass rose showing drone yaw heading."""

    def __init__(self, size: int = 120, parent=None):
        super().__init__(parent)
        self._heading = 0.0   # degrees, 0 = North
        self.setFixedSize(size, size)

    def set_heading(self, degrees: float) -> None:
        self._heading = degrees % 360
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        r = min(w, h) / 2 - 8

        # Outer ring
        pen = QPen(QColor(COLORS['border']))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(QColor(COLORS['bg_card']))
        painter.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        # Cardinal marks
        font = QFont("Consolas", max(6, int(r * 0.18)))
        font.setBold(True)
        painter.setFont(font)
        for angle, letter in [(0, 'N'), (90, 'E'), (180, 'S'), (270, 'W')]:
            rad = math.radians(angle - self._heading - 90)
            tx = cx + (r - 10) * math.cos(rad) - 5
            ty = cy + (r - 10) * math.sin(rad) + 5
            color = COLORS['accent_teal'] if letter == 'N' else COLORS['text_secondary']
            painter.setPen(QColor(color))
            painter.drawText(QRectF(tx - 6, ty - 10, 16, 14),
                             Qt.AlignmentFlag.AlignCenter, letter)

        # North arrow (teal)
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._heading)
        arrow_n = QPolygonF([
            QPointF(0, -r * 0.55),
            QPointF(-r * 0.08, 0),
            QPointF(r * 0.08, 0),
        ])
        arrow_s = QPolygonF([
            QPointF(0, r * 0.55),
            QPointF(-r * 0.08, 0),
            QPointF(r * 0.08, 0),
        ])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(COLORS['accent_teal']))
        painter.drawPolygon(arrow_n)
        painter.setBrush(QColor(COLORS['text_secondary']))
        painter.drawPolygon(arrow_s)
        # Center dot
        painter.setBrush(QColor(COLORS['text_primary']))
        painter.drawEllipse(QRectF(-4, -4, 8, 8))
        painter.restore()

        # Heading text
        pen2 = QPen(QColor(COLORS['accent_teal']))
        painter.setPen(pen2)
        font2 = QFont("Consolas", max(6, int(r * 0.16)))
        painter.setFont(font2)
        painter.drawText(QRectF(cx - r, cy + r * 0.55, r * 2, 20),
                         Qt.AlignmentFlag.AlignCenter,
                         f"{int(self._heading):03d}°")
