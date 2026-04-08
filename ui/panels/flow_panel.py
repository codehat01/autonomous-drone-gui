"""
FlowPanel — Optical Flow & Motion Detection panel.

Directly derived from read_motion_flow_data.py (EMA filter, deltaX/Y/motion)
and vx-vy-calculation-from-flow-and-tof.py (velocity calculation).

Displays:
  - Live pyqtgraph plots: Delta X, Delta Y, Motion Detection flag
  - EMA-filtered values (alpha=0.2, matching the Python-Script)
  - Raw vs filtered toggle
  - Computed Vx, Vy from flow + height
  - Motion detection status badge
"""
from collections import deque

import pyqtgraph as pg
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                              QLabel, QFrame, QPushButton)
from PyQt6.QtCore import pyqtSlot

from utils.theme import COLORS, card_style
from utils.config import EMA_ALPHA, VELOCITY_CONSTANT, VELOCITY_THRESHOLD
from ui.widgets.status_badge import StatusBadge

HISTORY = 200


def _calculate_velocity(delta_value: float, altitude: float) -> float:
    """
    Convert optical flow delta → linear velocity.
    Formula from test_optical_flow_sensor.py:
        velocity = delta * altitude * (5.4° in rad / (30 pixels × 0.01s))
    """
    if altitude <= 0:
        return 0.0
    return delta_value * altitude * VELOCITY_CONSTANT


class FlowPanel(QWidget):
    """
    Optical flow data panel with EMA-filtered live plots.
    Plots: Delta X (blue), Delta Y (red), Motion flag (green) — 3-subplot layout
    matching read_motion_flow_data.py.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # EMA state — matches read_motion_flow_data.py
        self._ema_dx = 0.0
        self._ema_dy = 0.0
        self._current_height = 0.0

        self._hist_dx = deque([0.0] * HISTORY, maxlen=HISTORY)
        self._hist_dy = deque([0.0] * HISTORY, maxlen=HISTORY)
        self._hist_mo = deque([0.0] * HISTORY, maxlen=HISTORY)
        self._hist_vx = deque([0.0] * HISTORY, maxlen=HISTORY)
        self._hist_vy = deque([0.0] * HISTORY, maxlen=HISTORY)

        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setStyleSheet(card_style())
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("OPTICAL FLOW SENSOR")
        title.setObjectName("panel_title")
        hdr.addWidget(title)
        hdr.addStretch()
        self._motion_badge = StatusBadge("NO MOTION", active=False)
        hdr.addWidget(self._motion_badge)
        layout.addLayout(hdr)

        # Live value row
        val_row = QHBoxLayout()
        self._dx_lbl  = self._make_val("ΔX", COLORS['accent_teal'])
        self._dy_lbl  = self._make_val("ΔY", COLORS['accent_purple'])
        self._vx_lbl  = self._make_val("Vx", COLORS['accent_amber'])
        self._vy_lbl  = self._make_val("Vy", COLORS['accent_green'])
        self._h_lbl   = self._make_val("H", COLORS['text_secondary'])
        for w in [self._dx_lbl, self._dy_lbl, self._vx_lbl, self._vy_lbl, self._h_lbl]:
            val_row.addWidget(w)
        layout.addLayout(val_row)

        # ── Plot 1: Delta X ──────────────────────────────────────────────────
        self._plot_dx = pg.PlotWidget(title="Delta X (Flow X)  [EMA filtered]")
        self._plot_dx.setBackground(COLORS['bg_card'])
        self._plot_dx.setMaximumHeight(90)
        self._plot_dx.showGrid(x=False, y=True, alpha=0.2)
        self._plot_dx.getPlotItem().getAxis('left').setTextPen(COLORS['text_secondary'])
        self._plot_dx.getPlotItem().getAxis('bottom').setTextPen(COLORS['text_secondary'])
        self._curve_dx = self._plot_dx.plot(
            pen=pg.mkPen(COLORS['accent_teal'], width=2), name="ΔX")
        layout.addWidget(self._plot_dx)

        # ── Plot 2: Delta Y ──────────────────────────────────────────────────
        self._plot_dy = pg.PlotWidget(title="Delta Y (Flow Y)  [EMA filtered]")
        self._plot_dy.setBackground(COLORS['bg_card'])
        self._plot_dy.setMaximumHeight(90)
        self._plot_dy.showGrid(x=False, y=True, alpha=0.2)
        self._plot_dy.getPlotItem().getAxis('left').setTextPen(COLORS['text_secondary'])
        self._plot_dy.getPlotItem().getAxis('bottom').setTextPen(COLORS['text_secondary'])
        self._curve_dy = self._plot_dy.plot(
            pen=pg.mkPen(COLORS['accent_purple'], width=2), name="ΔY")
        layout.addWidget(self._plot_dy)

        # ── Plot 3: Motion detection flag ────────────────────────────────────
        self._plot_mo = pg.PlotWidget(title="Motion Detected Flag")
        self._plot_mo.setBackground(COLORS['bg_card'])
        self._plot_mo.setMaximumHeight(70)
        self._plot_mo.showGrid(x=False, y=True, alpha=0.2)
        self._plot_mo.getPlotItem().getAxis('left').setTextPen(COLORS['text_secondary'])
        self._plot_mo.getPlotItem().getAxis('bottom').setTextPen(COLORS['text_secondary'])
        self._plot_mo.setYRange(-0.1, 1.2)
        self._curve_mo = self._plot_mo.plot(
            pen=pg.mkPen(COLORS['accent_green'], width=2),
            fillLevel=0,
            brush=pg.mkBrush(COLORS['accent_green'] + "33"),
            name="Motion")
        layout.addWidget(self._plot_mo)

        root.addWidget(card)

    def clear_state(self) -> None:
        """Reset all plots and labels to zero on disconnect."""
        self._ema_dx = 0.0
        self._ema_dy = 0.0
        self._hist_dx = deque([0.0] * HISTORY, maxlen=HISTORY)
        self._hist_dy = deque([0.0] * HISTORY, maxlen=HISTORY)
        self._hist_mo = deque([0.0] * HISTORY, maxlen=HISTORY)
        self._hist_vx = deque([0.0] * HISTORY, maxlen=HISTORY)
        self._hist_vy = deque([0.0] * HISTORY, maxlen=HISTORY)
        self._curve_dx.setData([0.0] * HISTORY)
        self._curve_dy.setData([0.0] * HISTORY)
        self._curve_mo.setData([0.0] * HISTORY)
        self._dx_lbl.setText("ΔX  --")
        self._dy_lbl.setText("ΔY  --")
        self._vx_lbl.setText("Vx  --")
        self._vy_lbl.setText("Vy  --")
        self._h_lbl.setText("H  --")
        self._motion_badge.set_label("NO MOTION")
        self._motion_badge.set_active(False)

    # ── Update slot ──────────────────────────────────────────────────────────

    @pyqtSlot(float, float, float, float)
    def set_flow(self, delta_x: float, delta_y: float,
                 motion: float, height: float) -> None:
        """
        Called with raw motion.deltaX, motion.deltaY, motion.motion, stateEstimate.z.
        Applies EMA filter (alpha=0.2) — same as read_motion_flow_data.py.
        """
        self._current_height = height

        # EMA filter — exact match to Python-Script
        self._ema_dx = EMA_ALPHA * delta_x + (1 - EMA_ALPHA) * self._ema_dx
        self._ema_dy = EMA_ALPHA * delta_y + (1 - EMA_ALPHA) * self._ema_dy

        # Velocity calculation — same as vx-vy-calculation-from-flow-and-tof.py
        vx = _calculate_velocity(self._ema_dx, height)
        vy = _calculate_velocity(self._ema_dy, height)
        if abs(vx) < VELOCITY_THRESHOLD:
            vx = 0.0
        if abs(vy) < VELOCITY_THRESHOLD:
            vy = 0.0

        # Append to histories
        self._hist_dx.append(self._ema_dx)
        self._hist_dy.append(self._ema_dy)
        self._hist_mo.append(float(motion))
        self._hist_vx.append(vx)
        self._hist_vy.append(vy)

        # Update plots
        self._curve_dx.setData(list(self._hist_dx))
        self._curve_dy.setData(list(self._hist_dy))
        self._curve_mo.setData(list(self._hist_mo))

        # Update value labels
        self._dx_lbl.setText(f"ΔX  {self._ema_dx:.2f}")
        self._dy_lbl.setText(f"ΔY  {self._ema_dy:.2f}")
        self._vx_lbl.setText(f"Vx  {vx:.3f}m/s")
        self._vy_lbl.setText(f"Vy  {vy:.3f}m/s")
        self._h_lbl.setText(f"H  {height:.2f}m")

        # Motion badge
        detected = motion > 0
        self._motion_badge.set_label("MOTION" if detected else "NO MOTION")
        self._motion_badge.set_active(detected)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _make_val(self, label: str, color: str) -> QLabel:
        lbl = QLabel(f"{label}  --")
        lbl.setObjectName("value_small")
        lbl.setStyleSheet(
            f"color: {color}; font-weight: bold; "
            "border-radius: 4px; padding: 2px 6px;")
        return lbl
