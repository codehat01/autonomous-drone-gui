"""
PositionPanel — 2D dead-reckoning position tracking panel.

Directly derived from position-tracking-graph.py:
  - Trapezoidal velocity → position integration
  - Drift compensation (gentle pull to zero when slow)
  - 2D position trajectory pyqtgraph scatter + current-position marker
  - Velocity history sub-plots (Vx blue, Vy red)
  - Reset position button

All constants match the Python-Script exactly:
    DRIFT_COMPENSATION_RATE = 0.001
    VELOCITY_THRESHOLD = 0.008
    MAX_POSITION_ERROR = 2.0
"""
import math
import time
from collections import deque

import pyqtgraph as pg
import numpy as np

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                              QLabel, QFrame, QPushButton)
from PyQt6.QtCore import pyqtSlot

from utils.theme import COLORS, card_style

# === Constants from position-tracking-graph.py ===
DRIFT_COMPENSATION_RATE = 0.001
VELOCITY_THRESHOLD      = 0.008
MAX_POSITION_ERROR      = 2.0
HISTORY = 300


class PositionPanel(QWidget):
    """
    Live 2D position tracking panel with:
      - Top: Vx (blue) / Vy (red) time-series plots
      - Bottom: 2D X-Y trajectory scatter + current marker + origin
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Position state — matches position-tracking-graph.py globals
        self._pos_x = 0.0
        self._pos_y = 0.0
        self._drift_x = 0.0
        self._drift_y = 0.0
        self._last_t: float | None = None

        # Trajectory history (never trimmed — full path)
        self._traj_x: list[float] = [0.0]
        self._traj_y: list[float] = [0.0]

        # Rolling velocity history
        self._hist_vx = deque([0.0] * HISTORY, maxlen=HISTORY)
        self._hist_vy = deque([0.0] * HISTORY, maxlen=HISTORY)

        self._setup_ui()

    # ── UI setup ─────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setStyleSheet(card_style())
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # Header row
        hdr = QHBoxLayout()
        title = QLabel("2D POSITION TRACKER")
        title.setObjectName("panel_title")
        hdr.addWidget(title)
        hdr.addStretch()
        self._reset_btn = QPushButton("RESET (0,0)")
        self._reset_btn.setFixedHeight(24)
        self._reset_btn.clicked.connect(self.reset_position)
        hdr.addWidget(self._reset_btn)
        layout.addLayout(hdr)

        # Sub-label
        sub = QLabel("Dead Reckoning  |  Trapezoidal Integration  |  Drift Compensation")
        sub.setObjectName("value_small")
        layout.addWidget(sub)

        # Value readout row
        val_row = QHBoxLayout()
        self._px_lbl = self._val_lbl("Pos X", COLORS['accent_teal'])
        self._py_lbl = self._val_lbl("Pos Y", COLORS['accent_purple'])
        self._vx_lbl = self._val_lbl("Vx",    COLORS['text_secondary'])
        self._vy_lbl = self._val_lbl("Vy",    COLORS['text_secondary'])
        for w in [self._px_lbl, self._py_lbl, self._vx_lbl, self._vy_lbl]:
            val_row.addWidget(w)
        layout.addLayout(val_row)

        # ── Velocity X plot ────────────────────────────────────────────────
        self._plt_vx = pg.PlotWidget(title="Velocity X  (m/s)")
        self._plt_vx.setBackground(COLORS['bg_card'])
        self._plt_vx.setMaximumHeight(110)
        self._plt_vx.showGrid(x=False, y=True, alpha=0.2)
        self._plt_vx.getPlotItem().getAxis('left').setTextPen(COLORS['text_secondary'])
        self._plt_vx.getPlotItem().getAxis('bottom').setTextPen(COLORS['text_secondary'])
        self._curve_vx = self._plt_vx.plot(
            pen=pg.mkPen(COLORS['accent_teal'], width=2))
        layout.addWidget(self._plt_vx)

        # ── Velocity Y plot ────────────────────────────────────────────────
        self._plt_vy = pg.PlotWidget(title="Velocity Y  (m/s)")
        self._plt_vy.setBackground(COLORS['bg_card'])
        self._plt_vy.setMaximumHeight(110)
        self._plt_vy.showGrid(x=False, y=True, alpha=0.2)
        self._plt_vy.getPlotItem().getAxis('left').setTextPen(COLORS['text_secondary'])
        self._plt_vy.getPlotItem().getAxis('bottom').setTextPen(COLORS['text_secondary'])
        self._curve_vy = self._plt_vy.plot(
            pen=pg.mkPen(COLORS['accent_purple'], width=2))
        layout.addWidget(self._plt_vy)

        # ── 2D position scatter plot ───────────────────────────────────────
        self._plt_2d = pg.PlotWidget(title="2D Trajectory  (top-down)")
        self._plt_2d.setBackground(COLORS['bg_card'])
        self._plt_2d.showGrid(x=True, y=True, alpha=0.15)
        self._plt_2d.setAspectLocked(True)
        self._plt_2d.getPlotItem().getAxis('left').setTextPen(COLORS['text_secondary'])
        self._plt_2d.getPlotItem().getAxis('bottom').setTextPen(COLORS['text_secondary'])
        self._plt_2d.getPlotItem().setLabel('left', 'Y  (m)')
        self._plt_2d.getPlotItem().setLabel('bottom', 'X  (m)')

        # Origin marker (yellow dot with black edge — matches Python-Script)
        origin = pg.ScatterPlotItem(
            [0], [0],
            symbol='o', size=12,
            pen=pg.mkPen('k', width=2),
            brush=pg.mkBrush('y'),
        )
        self._plt_2d.addItem(origin)

        # Trajectory line (purple)
        self._traj_curve = self._plt_2d.plot(
            pen=pg.mkPen(COLORS['accent_purple'], width=2, alpha=180),
        )

        # Current-position marker (red dot — matches Python-Script "ro")
        self._cur_marker = pg.ScatterPlotItem(
            [0], [0],
            symbol='o', size=10,
            pen=pg.mkPen(None),
            brush=pg.mkBrush(COLORS['accent_red']),
        )
        self._plt_2d.addItem(self._cur_marker)

        layout.addWidget(self._plt_2d, stretch=1)

        root.addWidget(card)

    # ── Public slot ───────────────────────────────────────────────────────────

    @pyqtSlot(float, float)
    def set_velocity(self, vx: float, vy: float) -> None:
        """
        Integrate (vx, vy) → position using trapezoidal integration + drift
        compensation.  Identical algorithm to position-tracking-graph.py.
        """
        now = time.monotonic()

        if self._last_t is not None:
            dt = now - self._last_t
            if 0.001 <= dt <= 0.1:
                # Apply threshold (same as Python-Script)
                vx_t = vx if abs(vx) >= VELOCITY_THRESHOLD else 0.0
                vy_t = vy if abs(vy) >= VELOCITY_THRESHOLD else 0.0

                # Trapezoidal integration
                self._pos_x += vx_t * dt
                self._pos_y += vy_t * dt

                # Drift compensation — matches position-tracking-graph.py
                speed = math.sqrt(vx_t * vx_t + vy_t * vy_t)
                if speed < VELOCITY_THRESHOLD * 2:
                    self._pos_x -= self._pos_x * DRIFT_COMPENSATION_RATE * dt
                    self._pos_y -= self._pos_y * DRIFT_COMPENSATION_RATE * dt

                # Clamp
                self._pos_x = max(-MAX_POSITION_ERROR,
                                  min(MAX_POSITION_ERROR, self._pos_x))
                self._pos_y = max(-MAX_POSITION_ERROR,
                                  min(MAX_POSITION_ERROR, self._pos_y))

                # Append to trajectory
                self._traj_x.append(self._pos_x)
                self._traj_y.append(self._pos_y)

        self._last_t = now

        # Update velocity histories
        self._hist_vx.append(vx)
        self._hist_vy.append(vy)

        # Refresh plots
        self._curve_vx.setData(list(self._hist_vx))
        self._curve_vy.setData(list(self._hist_vy))
        self._traj_curve.setData(self._traj_x, self._traj_y)
        self._cur_marker.setData([self._pos_x], [self._pos_y])

        # Refresh labels
        self._px_lbl.setText(f"Pos X  {self._pos_x:.3f} m")
        self._py_lbl.setText(f"Pos Y  {self._pos_y:.3f} m")
        self._vx_lbl.setText(f"Vx  {vx:.3f} m/s")
        self._vy_lbl.setText(f"Vy  {vy:.3f} m/s")

    @pyqtSlot()
    def reset_position(self) -> None:
        """Reset to origin — matches reset_position() in position-tracking-graph.py."""
        self._pos_x = 0.0
        self._pos_y = 0.0
        self._drift_x = 0.0
        self._drift_y = 0.0
        self._last_t = None
        self._traj_x = [0.0]
        self._traj_y = [0.0]
        self._traj_curve.setData(self._traj_x, self._traj_y)
        self._cur_marker.setData([0.0], [0.0])
        self._px_lbl.setText("Pos X  0.000 m")
        self._py_lbl.setText("Pos Y  0.000 m")

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _val_lbl(self, label: str, color: str) -> QLabel:
        lbl = QLabel(f"{label}  --")
        lbl.setObjectName("value_small")
        lbl.setStyleSheet(
            f"color: {color}; font-weight: bold; "
            "border-radius: 4px; padding: 2px 6px;")
        return lbl
