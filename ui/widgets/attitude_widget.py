"""
AttitudeWidget — 3D artificial horizon / attitude indicator.

Inspired by cfclient's attitude indicator and Mission Planner's HUD.
Uses QPainter to render:
  - Sky/ground split that rotates with roll and shifts with pitch
  - Horizon line with roll angle markings
  - Aircraft silhouette (fixed centre cross-hair)
  - Roll arc with degree markings
  - Pitch ladder lines
  - Digital readout: Roll / Pitch / Yaw values
"""
import math
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import (QPainter, QColor, QPen, QBrush, QFont,
                          QPainterPath, QLinearGradient, QConicalGradient)


class AttitudeWidget(QWidget):
    """
    Artificial horizon widget — reacts to roll, pitch, yaw.

    Call update_attitude(roll_deg, pitch_deg, yaw_deg) to refresh.
    """

    SKY_TOP    = QColor("#1a3a6b")
    SKY_BOT    = QColor("#2d6abf")
    GND_TOP    = QColor("#7a4d1e")
    GND_BOT    = QColor("#3d2510")
    HORIZON    = QColor("#ffffff")
    ACCENT     = QColor("#00d4aa")
    RED        = QColor("#ef4444")
    AMBER      = QColor("#f59e0b")
    TEXT_COLOR = QColor("#f1f5f9")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._roll  = 0.0
        self._pitch = 0.0
        self._yaw   = 0.0
        self.setMinimumSize(240, 240)

    def update_attitude(self, roll: float, pitch: float, yaw: float) -> None:
        self._roll  = roll
        self._pitch = pitch
        self._yaw   = yaw
        self.update()

    # ── Paint ──────────────────────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2.0, h / 2.0
        radius = min(w, h) / 2.0 - 4

        # Clip to circle
        clip = QPainterPath()
        clip.addEllipse(QPointF(cx, cy), radius, radius)
        p.setClipPath(clip)

        # ── Sky / ground fill (rotated by roll, shifted by pitch) ──────────────
        p.save()
        p.translate(cx, cy)
        p.rotate(self._roll)

        pitch_shift = (self._pitch / 90.0) * radius  # pixels per 90°

        # Sky gradient
        sky_grad = QLinearGradient(0, -radius, 0, pitch_shift)
        sky_grad.setColorAt(0.0, self.SKY_TOP)
        sky_grad.setColorAt(1.0, self.SKY_BOT)
        p.fillRect(int(-radius), int(-radius * 2), int(radius * 2),
                   int(radius * 2 + pitch_shift), QBrush(sky_grad))

        # Ground gradient
        gnd_grad = QLinearGradient(0, pitch_shift, 0, radius)
        gnd_grad.setColorAt(0.0, self.GND_TOP)
        gnd_grad.setColorAt(1.0, self.GND_BOT)
        p.fillRect(int(-radius), int(pitch_shift), int(radius * 2),
                   int(radius * 2), QBrush(gnd_grad))

        # Horizon line
        p.setPen(QPen(self.HORIZON, 2.5))
        p.drawLine(int(-radius), int(pitch_shift), int(radius), int(pitch_shift))

        # ── Pitch ladder ──────────────────────────────────────────────────────
        p.setPen(QPen(self.HORIZON, 1.5))
        font = QFont("Consolas", 7)
        p.setFont(font)
        for deg in range(-30, 35, 5):
            if deg == 0:
                continue
            y_pos = pitch_shift - (deg / 90.0) * radius
            bar_w = radius * (0.35 if deg % 10 == 0 else 0.2)
            p.drawLine(int(-bar_w), int(y_pos), int(bar_w), int(y_pos))
            if deg % 10 == 0:
                p.setPen(QPen(self.TEXT_COLOR, 1))
                p.drawText(QPointF(bar_w + 4, y_pos + 4), f"{deg}°")
                p.setPen(QPen(self.HORIZON, 1.5))

        p.restore()

        # ── Roll arc (outside clip but masked) ────────────────────────────────
        p.save()
        p.translate(cx, cy)
        pen = QPen(self.ACCENT, 2)
        p.setPen(pen)
        arc_r = radius - 8
        # Draw roll tick marks at 0, ±10, ±20, ±30, ±45, ±60
        for angle in [-60, -45, -30, -20, -10, 0, 10, 20, 30, 45, 60]:
            rad = math.radians(angle - 90)
            inner = arc_r - (10 if angle % 30 == 0 else 6)
            outer = arc_r
            p.drawLine(
                int(inner * math.cos(rad)), int(inner * math.sin(rad)),
                int(outer * math.cos(rad)), int(outer * math.sin(rad)),
            )

        # Roll indicator triangle
        p.save()
        p.rotate(self._roll)
        p.setBrush(QBrush(self.ACCENT))
        p.setPen(Qt.PenStyle.NoPen)
        tri = QPainterPath()
        tri.moveTo(0, -(arc_r - 2))
        tri.lineTo(-7, -(arc_r - 14))
        tri.lineTo(7, -(arc_r - 14))
        tri.closeSubpath()
        p.drawPath(tri)
        p.restore()

        p.restore()

        # ── Fixed aircraft crosshair (always centred) ──────────────────────────
        p.save()
        p.translate(cx, cy)
        p.setPen(QPen(self.AMBER, 3, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap))
        # Left wing
        p.drawLine(int(-radius * 0.45), 0, int(-radius * 0.15), 0)
        p.drawLine(int(-radius * 0.15), 0, int(-radius * 0.15), int(radius * 0.12))
        # Right wing
        p.drawLine(int(radius * 0.15), 0, int(radius * 0.45), 0)
        p.drawLine(int(radius * 0.15), 0, int(radius * 0.15), int(radius * 0.12))
        # Centre dot
        p.setBrush(QBrush(self.AMBER))
        p.drawEllipse(QPointF(0, 0), 4, 4)
        p.restore()

        # ── Remove clip, draw border circle ───────────────────────────────────
        p.setClipping(False)
        p.setPen(QPen(self.ACCENT, 3))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), radius, radius)

        # ── Digital readouts ──────────────────────────────────────────────────
        font = QFont("Consolas", 9, QFont.Weight.Bold)
        p.setFont(font)
        p.setPen(QPen(self.TEXT_COLOR))
        p.drawText(4, h - 48, f"R  {self._roll:+.1f}°")
        p.drawText(4, h - 32, f"P  {self._pitch:+.1f}°")
        p.drawText(4, h - 16, f"Y  {self._yaw:.1f}°")

        # ── Yaw compass strip at bottom ───────────────────────────────────────
        self._draw_yaw_strip(p, w, h)

    def _draw_yaw_strip(self, p: QPainter, w: int, h: int) -> None:
        """Draw a small compass strip showing current heading."""
        strip_y = h - 10
        strip_h = 14
        p.setPen(QPen(self.ACCENT, 1))
        p.setFont(QFont("Consolas", 8))
        yaw = self._yaw % 360
        for offset in range(-60, 65, 10):
            heading = (yaw + offset) % 360
            x = w / 2 + (offset / 120.0) * (w * 0.6)
            tick_h = 6 if heading % 30 == 0 else 3
            p.drawLine(int(x), strip_y - tick_h, int(x), strip_y)
            if heading % 30 == 0:
                lbl = {0: "N", 90: "E", 180: "S", 270: "W"}.get(int(heading), str(int(heading)))
                p.drawText(int(x) - 8, strip_y - tick_h - 2, lbl)
