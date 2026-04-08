import pyqtgraph as pg
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                              QLabel, QProgressBar, QFrame)
from PyQt6.QtCore import pyqtSlot
from utils.theme import COLORS, card_style
from ui.widgets.gauge_widget import GaugeWidget
from ui.widgets.compass_widget import CompassWidget
from models.drone_state import DroneState

pg.setConfigOptions(antialias=True, background=COLORS['bg_card'])


class TelemetryPanel(QWidget):
    """
    Drone telemetry panel showing battery, IMU angles, motor PWMs, height, velocity.
    All values updated via set_state(DroneState) slot.
    """

    HISTORY_LEN = 300   # ~30s at 10fps updates

    def __init__(self, parent=None):
        super().__init__(parent)
        self._vx_history = [0.0] * self.HISTORY_LEN
        self._vy_history = [0.0] * self.HISTORY_LEN
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setStyleSheet(card_style())
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("TELEMETRY")
        title.setObjectName("panel_title")
        layout.addWidget(title)

        # ── Row 1: Battery + Pitch + Roll + Compass ────────────────────────────
        gauges_row = QHBoxLayout()
        self._battery_gauge = GaugeWidget("Battery", "%", 0, 100, size=100)
        self._pitch_gauge   = GaugeWidget("Pitch",   "°", -45, 45, size=100)
        self._roll_gauge    = GaugeWidget("Roll",    "°", -45, 45, size=100)
        self._compass       = CompassWidget(size=100)

        for w in [self._battery_gauge, self._pitch_gauge,
                  self._roll_gauge, self._compass]:
            gauges_row.addWidget(w)
        layout.addLayout(gauges_row)

        # ── Battery voltage label ──────────────────────────────────────────────
        self._bat_v_label = QLabel("-- V")
        self._bat_v_label.setObjectName("value_medium")
        layout.addWidget(self._bat_v_label)

        # ── Height bar ─────────────────────────────────────────────────────────
        height_row = QHBoxLayout()
        h_lbl = QLabel("Height:")
        h_lbl.setObjectName("value_small")
        self._height_bar = QProgressBar()
        self._height_bar.setRange(0, 150)   # 0 – 1.5m × 100
        self._height_bar.setValue(0)
        self._height_bar.setFormat("")       # value shown in the label next to bar
        self._height_bar.setFixedHeight(18)
        self._height_val = QLabel("0.00 m")
        self._height_val.setObjectName("value_small")
        self._height_val.setFixedWidth(50)
        height_row.addWidget(h_lbl)
        height_row.addWidget(self._height_bar)
        height_row.addWidget(self._height_val)
        layout.addLayout(height_row)

        # ── Motor PWM bars ─────────────────────────────────────────────────────
        motors_lbl = QLabel("MOTORS  (PWM 0–60000)")
        motors_lbl.setObjectName("value_small")
        layout.addWidget(motors_lbl)

        self._motor_bars = []
        motor_labels = ["M1", "M2", "M3", "M4"]
        for name in motor_labels:
            row = QHBoxLayout()
            lbl = QLabel(name)
            lbl.setObjectName("value_small")
            lbl.setFixedWidth(20)
            bar = QProgressBar()
            bar.setObjectName("motor_bar")
            bar.setRange(0, 60000)
            bar.setValue(0)
            bar.setFormat("%v")
            bar.setFixedHeight(14)
            val_lbl = QLabel("0")
            val_lbl.setObjectName("value_small")
            val_lbl.setFixedWidth(45)
            row.addWidget(lbl)
            row.addWidget(bar)
            row.addWidget(val_lbl)
            layout.addLayout(row)
            self._motor_bars.append((bar, val_lbl))

        # ── Velocity mini-plots ────────────────────────────────────────────────
        vel_lbl = QLabel("VELOCITY")
        vel_lbl.setObjectName("value_small")
        layout.addWidget(vel_lbl)

        plots_row = QHBoxLayout()
        self._vx_plot = pg.PlotWidget(title="Vx (m/s)")
        self._vy_plot = pg.PlotWidget(title="Vy (m/s)")
        for plot in [self._vx_plot, self._vy_plot]:
            plot.setBackground(COLORS['bg_card'])
            plot.setMaximumHeight(100)
            plot.getPlotItem().showGrid(x=False, y=True, alpha=0.3)
            plot.getPlotItem().getAxis('left').setTextPen(COLORS['text_secondary'])
            plot.getPlotItem().getAxis('bottom').setTextPen(COLORS['text_secondary'])
            plot.getPlotItem().titleLabel.setAttr('color', COLORS['text_secondary'])
        self._vx_curve = self._vx_plot.plot(pen=pg.mkPen(COLORS['accent_teal'], width=2))
        self._vy_curve = self._vy_plot.plot(pen=pg.mkPen(COLORS['accent_purple'], width=2))
        plots_row.addWidget(self._vx_plot)
        plots_row.addWidget(self._vy_plot)
        layout.addLayout(plots_row)

        root.addWidget(card)

    def clear_state(self) -> None:
        """Reset all displays to disconnected state."""
        self._battery_gauge.set_value(0)
        self._pitch_gauge.set_value(0)
        self._roll_gauge.set_value(0)
        self._compass.set_heading(0)
        self._bat_v_label.setText("-- V")
        self._height_bar.setValue(0)
        self._height_val.setText("0.00 m")
        for bar, lbl in self._motor_bars:
            bar.setValue(0)
            lbl.setText("0")
        self._vx_history = [0.0] * self.HISTORY_LEN
        self._vy_history = [0.0] * self.HISTORY_LEN
        self._vx_curve.setData(self._vx_history)
        self._vy_curve.setData(self._vy_history)

    @pyqtSlot(object)   # DroneState
    def set_state(self, state: DroneState) -> None:
        self._battery_gauge.set_value(state.battery_percent)
        self._pitch_gauge.set_value(state.pitch)
        self._roll_gauge.set_value(state.roll)
        self._compass.set_heading(state.yaw)
        self._bat_v_label.setText(f"{state.battery_voltage:.2f} V")

        height_cm = int(state.height * 100)
        self._height_bar.setValue(min(height_cm, 150))
        self._height_val.setText(f"{state.height:.2f} m")

        for i, (bar, lbl) in enumerate(self._motor_bars):
            vals = [state.motor_m1, state.motor_m2, state.motor_m3, state.motor_m4]
            bar.setValue(vals[i])
            lbl.setText(str(vals[i]))

        self._vx_history.pop(0)
        self._vx_history.append(state.velocity_x)
        self._vy_history.pop(0)
        self._vy_history.append(state.velocity_y)
        self._vx_curve.setData(self._vx_history)
        self._vy_curve.setData(self._vy_history)
