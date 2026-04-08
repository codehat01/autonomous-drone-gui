"""
AnalyticsPage — Sensor data, graphs, and position tracking.

Derived from:
  - read_motion_flow_data.py        → FlowPanel (EMA deltaX/Y/motion)
  - position-tracking-graph.py     → PositionPanel (2D trajectory)
  - cflib_groundStation.py         → full telemetry graphs (pitch/roll/yaw + motors)
  - vx-vy-calculation-from-flow-and-tof.py → velocity plots

Layout (scrollable):
  Top row:   flow panel (left) | position 2D tracker (right, spans 2 cols)
  Bottom row: full telemetry log with all cflib_groundStation plots
"""
import math
from collections import deque

import pyqtgraph as pg
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                              QLabel, QFrame, QPushButton, QScrollArea,
                              QSizePolicy)
from PyQt6.QtCore import pyqtSlot, Qt

from utils.theme import COLORS, card_style, FONT_MONO
from ui.panels.flow_panel import FlowPanel
from ui.panels.position_panel import PositionPanel
from models.drone_state import DroneState

HISTORY = 300


class AnalyticsPage(QWidget):
    """
    Full analytics dashboard with all sensor graphs — scrollable.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hist = {
            'pitch':  deque([0.0] * HISTORY, maxlen=HISTORY),
            'roll':   deque([0.0] * HISTORY, maxlen=HISTORY),
            'yaw':    deque([0.0] * HISTORY, maxlen=HISTORY),
            'm1':     deque([0.0] * HISTORY, maxlen=HISTORY),
            'm2':     deque([0.0] * HISTORY, maxlen=HISTORY),
            'm3':     deque([0.0] * HISTORY, maxlen=HISTORY),
            'm4':     deque([0.0] * HISTORY, maxlen=HISTORY),
            'height': deque([0.0] * HISTORY, maxlen=HISTORY),
            'vbat':   deque([0.0] * HISTORY, maxlen=HISTORY),
        }
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Scroll area ───────────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        container.setMinimumSize(1100, 1000)
        inner = QVBoxLayout(container)
        inner.setContentsMargins(8, 8, 8, 8)
        inner.setSpacing(8)

        # Page title
        title = QLabel("SENSOR ANALYTICS  &  TELEMETRY GRAPHS")
        title.setStyleSheet(
            f"color: {COLORS['accent_teal']}; font-size: 15px; font-weight: bold; "
            f"font-family: {FONT_MONO}; letter-spacing: 2px;")
        inner.addWidget(title)

        # ── Row 0: Flow + Position ────────────────────────────────────────────
        top_row = QHBoxLayout()
        self.flow_panel     = FlowPanel()
        self.position_panel = PositionPanel()
        self.flow_panel.setMinimumHeight(340)
        self.position_panel.setMinimumHeight(340)
        top_row.addWidget(self.flow_panel,     stretch=1)
        top_row.addWidget(self.position_panel, stretch=2)
        inner.addLayout(top_row, stretch=3)

        # ── Row 1: cflib_groundStation graphs ─────────────────────────────────
        telem = self._build_telemetry_graphs()
        telem.setMinimumHeight(380)
        inner.addWidget(telem, stretch=2)

        scroll.setWidget(container)
        root.addWidget(scroll)

    def _build_telemetry_graphs(self) -> QFrame:
        """
        Full cflib_groundStation.py style telemetry graphs:
          - Pitch/Roll/Yaw (K_Pitch blue, K_Roll lightblue, K_Yaw darkblue)
          - Motor PWM M1-M4 (green, orange, teal, brown)
          - Battery voltage + Height
        """
        card = QFrame()
        card.setStyleSheet(card_style())
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        hdr = QHBoxLayout()
        t = QLabel("DRONE TELEMETRY GRAPHS  (cflib LogConfig — 10ms / 100Hz)")
        t.setObjectName("panel_title")
        hdr.addWidget(t)
        hdr.addStretch()
        sub = QLabel("stateEstimate.pitch/roll/yaw  ·  pwm.m1–m4  ·  pm.vbat  ·  stateEstimate.z")
        sub.setObjectName("value_small")
        hdr.addWidget(sub)
        layout.addLayout(hdr)

        grid = QGridLayout()
        grid.setSpacing(6)

        # ── IMU plot: Pitch (blue), Roll (lightblue), Yaw (darkblue) ──────────
        self._imu_plot = self._make_plot("IMU  —  Pitch / Roll / Yaw  (°)")
        self._curve_pitch = self._imu_plot.plot(
            pen=pg.mkPen('#1E90FF', width=2), name="K_Pitch")
        self._curve_roll  = self._imu_plot.plot(
            pen=pg.mkPen('#87CEEB', width=2), name="K_Roll")
        self._curve_yaw   = self._imu_plot.plot(
            pen=pg.mkPen('#00008B', width=2), name="K_Yaw")
        grid.addWidget(self._imu_plot, 0, 0)

        # ── Motor PWM plot: M1 green, M2 orange, M3 teal, M4 brown ────────────
        self._motor_plot = self._make_plot("MOTOR  —  M1 / M2 / M3 / M4  (PWM)")
        self._curve_m1 = self._motor_plot.plot(
            pen=pg.mkPen('#008000', width=2), name="M1")
        self._curve_m2 = self._motor_plot.plot(
            pen=pg.mkPen('#FFA500', width=2), name="M2")
        self._curve_m3 = self._motor_plot.plot(
            pen=pg.mkPen('#008080', width=2), name="M3")
        self._curve_m4 = self._motor_plot.plot(
            pen=pg.mkPen('#8B4513', width=2), name="M4")
        grid.addWidget(self._motor_plot, 0, 1)

        # ── Battery voltage plot ───────────────────────────────────────────────
        self._bat_plot = self._make_plot("BATTERY  —  pm.vbat  (V)")
        self._curve_vbat = self._bat_plot.plot(
            pen=pg.mkPen(COLORS['accent_green'], width=2), name="pm.vbat")
        grid.addWidget(self._bat_plot, 1, 0)

        # ── Height / ToF plot ──────────────────────────────────────────────────
        self._h_plot = self._make_plot("HEIGHT  —  stateEstimate.z  (m)")
        self._curve_height = self._h_plot.plot(
            pen=pg.mkPen(COLORS['accent_teal'], width=2), name="z")
        grid.addWidget(self._h_plot, 1, 1)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)
        layout.addLayout(grid, stretch=1)

        return card

    # ── Update slots ──────────────────────────────────────────────────────────

    def clear_state(self) -> None:
        """Reset all graphs to zero on disconnect."""
        for key in self._hist:
            self._hist[key] = deque([0.0] * HISTORY, maxlen=HISTORY)
        self._curve_pitch.setData([0.0] * HISTORY)
        self._curve_roll.setData([0.0] * HISTORY)
        self._curve_yaw.setData([0.0] * HISTORY)
        self._curve_m1.setData([0.0] * HISTORY)
        self._curve_m2.setData([0.0] * HISTORY)
        self._curve_m3.setData([0.0] * HISTORY)
        self._curve_m4.setData([0.0] * HISTORY)
        self._curve_vbat.setData([0.0] * HISTORY)
        self._curve_height.setData([0.0] * HISTORY)
        self.flow_panel.clear_state()
        self.position_panel.reset_position()

    @pyqtSlot(object)
    def set_state(self, state: DroneState) -> None:
        """Feed DroneState into all telemetry history buffers and update plots."""
        self._hist['pitch'].append(state.pitch)
        self._hist['roll'].append(state.roll)
        self._hist['yaw'].append(state.yaw)
        self._hist['m1'].append(state.motor_m1)
        self._hist['m2'].append(state.motor_m2)
        self._hist['m3'].append(state.motor_m3)
        self._hist['m4'].append(state.motor_m4)
        self._hist['height'].append(state.height)
        self._hist['vbat'].append(state.battery_voltage)

        self._curve_pitch.setData(list(self._hist['pitch']))
        self._curve_roll.setData(list(self._hist['roll']))
        self._curve_yaw.setData(list(self._hist['yaw']))

        self._curve_m1.setData(list(self._hist['m1']))
        self._curve_m2.setData(list(self._hist['m2']))
        self._curve_m3.setData(list(self._hist['m3']))
        self._curve_m4.setData(list(self._hist['m4']))

        self._curve_vbat.setData(list(self._hist['vbat']))
        self._curve_height.setData(list(self._hist['height']))

        # Forward to sub-panels
        self.position_panel.set_velocity(state.velocity_x, state.velocity_y)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _make_plot(self, title: str) -> pg.PlotWidget:
        pw = pg.PlotWidget(title=title)
        pw.setBackground(COLORS['bg_card'])
        pw.showGrid(x=False, y=True, alpha=0.18)
        pw.getPlotItem().getAxis('left').setTextPen(COLORS['text_secondary'])
        pw.getPlotItem().getAxis('bottom').setTextPen(COLORS['text_secondary'])
        pw.getPlotItem().titleLabel.setAttr('color', COLORS['text_secondary'])
        return pw
