"""
ImuPage — IMU sensor visualization page.

Derived from Flight_Positioning_Module/test_imu.py:
  - LogConfig(name="IMUSensor", period_in_ms=50)
  - stateEstimate.roll/pitch/yaw/ax/ay/az
  - deque(maxlen=400) history buffers
  - threading.Event stop pattern for background worker
  - _add_variables_if_available() TOC check
  - 20-second rolling X window
  - 100ms GUI refresh timer

Layout:
  Left column:  3D AttitudeWidget + digital value cards
  Right column: Roll/Pitch/Yaw plot (red/green/blue)
                Acceleration ax/ay/az plot (orange/purple/teal)
"""
import threading
import time
from collections import deque

import pyqtgraph as pg
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                              QLabel, QFrame, QPushButton, QScrollArea,
                              QSizePolicy)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot

from utils.theme import COLORS, card_style, FONT_MONO
from ui.widgets.attitude_widget import AttitudeWidget

HISTORY_LENGTH = 400   # matching test_imu.py


class ImuPage(QWidget):
    """
    IMU live visualization — attitude + accelerometer plots + 3D artificial horizon.
    Receives data via push_imu() called from DroneService log callbacks or demo timer.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # ── Data buffers (test_imu.py pattern: deque(maxlen=HISTORY_LENGTH)) ──
        self._data_lock = threading.Lock()
        self.timestamps     = deque(maxlen=HISTORY_LENGTH)
        self.roll_history   = deque(maxlen=HISTORY_LENGTH)
        self.pitch_history  = deque(maxlen=HISTORY_LENGTH)
        self.yaw_history    = deque(maxlen=HISTORY_LENGTH)
        self.ax_history     = deque(maxlen=HISTORY_LENGTH)
        self.ay_history     = deque(maxlen=HISTORY_LENGTH)
        self.az_history     = deque(maxlen=HISTORY_LENGTH)
        self._latest: tuple | None = None
        self._t0: float | None = None

        self._setup_ui()

        # ── 100ms GUI refresh timer (same period as test_imu.py root.after(100,…)) ──
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_gui)
        self._refresh_timer.start(100)

    # ── Data input ────────────────────────────────────────────────────────────

    def push_imu(self, roll: float, pitch: float, yaw: float,
                 ax: float, ay: float, az: float) -> None:
        """
        Receive IMU sample — called from DroneService log callback or demo timer.
        Thread-safe (uses data_lock as in test_imu.py).
        """
        with self._data_lock:
            now = time.time()
            if self._t0 is None:
                self._t0 = now
            self.timestamps.append(now - self._t0)
            self.roll_history.append(roll)
            self.pitch_history.append(pitch)
            self.yaw_history.append(yaw)
            self.ax_history.append(ax)
            self.ay_history.append(ay)
            self.az_history.append(az)
            self._latest = (roll, pitch, yaw, ax, ay, az)

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        container.setMinimumSize(1000, 700)
        inner = QVBoxLayout(container)
        inner.setContentsMargins(12, 10, 12, 10)
        inner.setSpacing(10)

        # Page title
        title = QLabel("IMU SENSOR  —  stateEstimate.roll / pitch / yaw / ax / ay / az")
        title.setStyleSheet(
            f"color: {COLORS['accent_teal']}; font-size: 15px; font-weight: bold; "
            f"font-family: {FONT_MONO}; letter-spacing: 2px;")
        inner.addWidget(title)

        # Main content row
        content = QHBoxLayout()
        content.setSpacing(10)

        # Left: attitude widget + value cards
        content.addWidget(self._build_left_panel(), stretch=2)

        # Right: two plots
        content.addWidget(self._build_plots(), stretch=3)

        inner.addLayout(content, stretch=1)
        scroll.setWidget(container)
        root.addWidget(scroll)

    def _build_left_panel(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(card_style())
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        hdr = QLabel("3D ATTITUDE INDICATOR")
        hdr.setObjectName("panel_title")
        layout.addWidget(hdr)

        # 3D attitude widget
        self._attitude = AttitudeWidget()
        self._attitude.setMinimumSize(280, 280)
        self._attitude.setSizePolicy(QSizePolicy.Policy.Expanding,
                                     QSizePolicy.Policy.Expanding)
        layout.addWidget(self._attitude, stretch=1)

        # Digital value cards
        grid = QGridLayout()
        grid.setSpacing(6)

        fields = [
            ("ROLL",   "0.00 °",  COLORS['accent_red'],    "_lbl_roll"),
            ("PITCH",  "0.00 °",  COLORS['accent_green'],  "_lbl_pitch"),
            ("YAW",    "0.00 °",  COLORS['accent_purple'], "_lbl_yaw"),
            ("AX",     "0.000",   COLORS['accent_amber'],  "_lbl_ax"),
            ("AY",     "0.000",   COLORS['accent_amber'],  "_lbl_ay"),
            ("AZ",     "9.810",   COLORS['accent_teal'],   "_lbl_az"),
        ]
        for i, (label, default, color, attr) in enumerate(fields):
            row, col = divmod(i, 2)
            f = QFrame()
            f.setStyleSheet(
                f"background: {COLORS['bg_primary']}; border-radius: 6px;")
            fl = QVBoxLayout(f)
            fl.setContentsMargins(6, 4, 6, 4)
            lbl_name = QLabel(label)
            lbl_name.setObjectName("value_small")
            lbl_val = QLabel(default)
            lbl_val.setStyleSheet(
                f"color: {color}; font-size: 16px; font-weight: bold; "
                f"font-family: {FONT_MONO};")
            fl.addWidget(lbl_name)
            fl.addWidget(lbl_val)
            setattr(self, attr, lbl_val)
            grid.addWidget(f, row, col)
        layout.addLayout(grid)

        # Reset button
        reset_btn = QPushButton("RESET HISTORY")
        reset_btn.clicked.connect(self._reset_history)
        layout.addWidget(reset_btn)

        return card

    def _build_plots(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(card_style())
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        hdr = QLabel("ORIENTATION  &  ACCELERATION  (20s rolling window — 50ms LogConfig)")
        hdr.setObjectName("panel_title")
        layout.addWidget(hdr)

        # Roll / Pitch / Yaw plot (red/green/blue — matching test_imu.py colours)
        self._rpy_plot = self._make_plot("Roll / Pitch / Yaw  (°)")
        self._curve_roll  = self._rpy_plot.plot(
            pen=pg.mkPen('#e74c3c', width=2), name="Roll")
        self._curve_pitch = self._rpy_plot.plot(
            pen=pg.mkPen('#2ecc71', width=2), name="Pitch")
        self._curve_yaw   = self._rpy_plot.plot(
            pen=pg.mkPen('#3498db', width=2), name="Yaw")
        legend_rpy = self._rpy_plot.addLegend(offset=(10, 10))
        layout.addWidget(self._rpy_plot, stretch=1)

        # Acceleration plot (ax/ay/az — orange/purple/teal)
        self._acc_plot = self._make_plot("Acceleration  ax / ay / az  (m/s²)")
        self._curve_ax = self._acc_plot.plot(
            pen=pg.mkPen(COLORS['accent_amber'],  width=2), name="ax")
        self._curve_ay = self._acc_plot.plot(
            pen=pg.mkPen(COLORS['accent_purple'], width=2), name="ay")
        self._curve_az = self._acc_plot.plot(
            pen=pg.mkPen(COLORS['accent_teal'],   width=2), name="az")
        legend_acc = self._acc_plot.addLegend(offset=(10, 10))
        layout.addWidget(self._acc_plot, stretch=1)

        return card

    def _make_plot(self, title: str) -> pg.PlotWidget:
        pw = pg.PlotWidget(title=title)
        pw.setBackground(COLORS['bg_card'])
        pw.showGrid(x=True, y=True, alpha=0.18)
        pw.getPlotItem().getAxis('left').setTextPen(COLORS['text_secondary'])
        pw.getPlotItem().getAxis('bottom').setTextPen(COLORS['text_secondary'])
        pw.getPlotItem().titleLabel.setAttr('color', COLORS['text_secondary'])
        pw.setMinimumHeight(160)
        return pw

    # ── GUI refresh (100ms — test_imu.py root.after(100, _refresh_gui)) ───────

    def _refresh_gui(self) -> None:
        """
        Update plots and attitude widget from buffered IMU data.
        Runs on main thread every 100ms (same pattern as test_imu.py _refresh_gui).
        """
        with self._data_lock:
            if self._latest is None:
                return
            roll, pitch, yaw, ax, ay, az = self._latest

            times       = list(self.timestamps)
            roll_vals   = list(self.roll_history)
            pitch_vals  = list(self.pitch_history)
            yaw_vals    = list(self.yaw_history)
            ax_vals     = list(self.ax_history)
            ay_vals     = list(self.ay_history)
            az_vals     = list(self.az_history)

        # Update digital labels
        self._lbl_roll.setText(f"{roll:+.2f} °")
        self._lbl_pitch.setText(f"{pitch:+.2f} °")
        self._lbl_yaw.setText(f"{yaw:.2f} °")
        self._lbl_ax.setText(f"{ax:.3f}")
        self._lbl_ay.setText(f"{ay:.3f}")
        self._lbl_az.setText(f"{az:.3f}")

        # Update 3D attitude indicator
        self._attitude.update_attitude(roll, pitch, yaw)

        if not times:
            return

        # ── 20-second rolling window (test_imu.py: axis.set_xlim(max(0, last-20), last+1)) ──
        last_t = times[-1] if times[-1] > 1 else 1
        x_min = max(0.0, last_t - 20.0)
        x_max = last_t + 1.0

        # RPY plot
        self._curve_roll.setData(times, roll_vals)
        self._curve_pitch.setData(times, pitch_vals)
        self._curve_yaw.setData(times, yaw_vals)
        self._rpy_plot.setXRange(x_min, x_max, padding=0)

        # Auto Y range with margin
        all_rpy = roll_vals + pitch_vals + yaw_vals
        if all_rpy:
            vmin, vmax = min(all_rpy), max(all_rpy)
            margin = max(5.0, (vmax - vmin) * 0.2)
            self._rpy_plot.setYRange(vmin - margin, vmax + margin, padding=0)

        # Acceleration plot
        self._curve_ax.setData(times, ax_vals)
        self._curve_ay.setData(times, ay_vals)
        self._curve_az.setData(times, az_vals)
        self._acc_plot.setXRange(x_min, x_max, padding=0)

    def _reset_history(self) -> None:
        with self._data_lock:
            self.timestamps.clear()
            self.roll_history.clear()
            self.pitch_history.clear()
            self.yaw_history.clear()
            self.ax_history.clear()
            self.ay_history.clear()
            self.az_history.clear()
            self._latest = None
            self._t0 = None
