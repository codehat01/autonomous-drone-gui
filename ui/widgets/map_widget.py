import math
from collections import deque
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QPointF, QRectF, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen, QPolygonF, QFont
from utils.theme import COLORS
from utils.config import ROOM_SIZE_METERS, MAP_TRAIL_LENGTH


class MapWidget(QWidget):
    """
    Indoor dead-reckoning position tracker.
    Displays a top-down grid map with drone position trail and heading arrow.
    Position units: meters relative to start point (origin = center).
    """

    GRID_LINES = 10

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pos_x = 0.0   # meters from origin
        self._pos_y = 0.0
        self._heading = 0.0  # degrees yaw
        self._trail: deque = deque(maxlen=MAP_TRAIL_LENGTH)
        self._room_size = ROOM_SIZE_METERS
        self.setMinimumSize(320, 320)

        # Repaint at 10fps — position data is slow
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(100)

    def add_position(self, x: float, y: float) -> None:
        self._pos_x = x
        self._pos_y = y
        self._trail.append((x, y))

    def set_heading(self, degrees: float) -> None:
        self._heading = degrees % 360

    def reset_position(self) -> None:
        self._pos_x = 0.0
        self._pos_y = 0.0
        self._trail.clear()
        self.update()

    def _world_to_canvas(self, x: float, y: float) -> QPointF:
        """Convert world meters to canvas pixels. Origin at center."""
        w, h = self.width(), self.height()
        scale = min(w, h) / self._room_size
        cx, cy = w / 2, h / 2
        return QPointF(cx + x * scale, cy - y * scale)   # y-up in world, y-down in screen

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        scale = min(w, h) / self._room_size

        # Background
        painter.fillRect(0, 0, w, h, QColor(COLORS['bg_card']))

        # Grid lines
        pen = QPen(QColor(COLORS['border']))
        pen.setWidth(1)
        painter.setPen(pen)
        step_m = self._room_size / self.GRID_LINES
        for i in range(self.GRID_LINES + 1):
            world_coord = -self._room_size / 2 + i * step_m
            # Vertical line
            p1 = self._world_to_canvas(world_coord, -self._room_size / 2)
            p2 = self._world_to_canvas(world_coord,  self._room_size / 2)
            painter.drawLine(p1.toPoint(), p2.toPoint())
            # Horizontal line
            p3 = self._world_to_canvas(-self._room_size / 2, world_coord)
            p4 = self._world_to_canvas( self._room_size / 2, world_coord)
            painter.drawLine(p3.toPoint(), p4.toPoint())

        # Room border
        border_pen = QPen(QColor(COLORS['accent_teal']))
        border_pen.setWidth(2)
        painter.setPen(border_pen)
        tl = self._world_to_canvas(-self._room_size / 2,  self._room_size / 2)
        br = self._world_to_canvas( self._room_size / 2, -self._room_size / 2)
        painter.drawRect(QRectF(tl, br))

        # Trail
        trail_list = list(self._trail)
        if len(trail_list) > 1:
            for i in range(1, len(trail_list)):
                alpha = int(255 * i / len(trail_list))
                trail_color = QColor(COLORS['accent_teal'])
                trail_color.setAlpha(alpha)
                trail_pen = QPen(trail_color)
                trail_pen.setWidth(2)
                painter.setPen(trail_pen)
                p1 = self._world_to_canvas(*trail_list[i - 1])
                p2 = self._world_to_canvas(*trail_list[i])
                painter.drawLine(p1.toPoint(), p2.toPoint())

        # Drone marker
        drone_pt = self._world_to_canvas(self._pos_x, self._pos_y)
        dx, dy = drone_pt.x(), drone_pt.y()

        # Heading arrow
        painter.save()
        painter.translate(dx, dy)
        painter.rotate(self._heading)
        arrow_size = 12
        arrow = QPolygonF([
            QPointF(0, -arrow_size),
            QPointF(-arrow_size * 0.4, arrow_size * 0.5),
            QPointF(0, 0),
            QPointF(arrow_size * 0.4, arrow_size * 0.5),
        ])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(COLORS['accent_teal']))
        painter.drawPolygon(arrow)
        painter.restore()

        # Drone circle
        drone_r = 8
        painter.setBrush(QColor(COLORS['accent_teal']))
        pen3 = QPen(QColor(COLORS['bg_primary']))
        pen3.setWidth(2)
        painter.setPen(pen3)
        painter.drawEllipse(QRectF(dx - drone_r, dy - drone_r, drone_r * 2, drone_r * 2))

        # Scale label bottom-left
        painter.setPen(QColor(COLORS['text_secondary']))
        font = QFont("Consolas", 9)
        painter.setFont(font)
        painter.drawText(QRectF(4, h - 20, 120, 16),
                         Qt.AlignmentFlag.AlignLeft,
                         f"Scale: {self._room_size:.0f}m x {self._room_size:.0f}m")

        # Position readout
        painter.setPen(QColor(COLORS['accent_teal']))
        painter.drawText(QRectF(w - 130, h - 20, 126, 16),
                         Qt.AlignmentFlag.AlignRight,
                         f"X:{self._pos_x:.2f}m  Y:{self._pos_y:.2f}m")
