from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QPainter, QColor, QRadialGradient


class LedIndicator(QWidget):
    """Pulsing circular LED indicator widget."""

    def __init__(self, color: str = "#00d4aa", size: int = 16, parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self._dim_color = QColor(color)
        self._dim_color.setAlphaF(0.25)
        self._active = False
        self._pulse_alpha = 255
        self._pulse_dir = -4

        self.setFixedSize(size, size)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._pulse_step)

    def set_state(self, active: bool) -> None:
        self._active = active
        if active:
            self._timer.start(30)
        else:
            self._timer.stop()
            self._pulse_alpha = 255
        self.update()

    def _pulse_step(self) -> None:
        self._pulse_alpha += self._pulse_dir * 3
        if self._pulse_alpha <= 60:
            self._pulse_dir = 4
        elif self._pulse_alpha >= 255:
            self._pulse_dir = -4
        self._pulse_alpha = max(60, min(255, self._pulse_alpha))
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        r = min(w, h) / 2 - 1

        if self._active:
            c = QColor(self._color)
            c.setAlpha(self._pulse_alpha)
            grad = QRadialGradient(cx, cy, r)
            grad.setColorAt(0.0, c)
            bright = QColor(self._color)
            bright.setAlpha(self._pulse_alpha)
            grad.setColorAt(0.5, bright)
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.setBrush(grad)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))
        else:
            painter.setBrush(self._dim_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(cx - r * 0.6, cy - r * 0.6, r * 1.2, r * 1.2))
