"""
ManeuverPage — Dead-Reckoning Position Hold + Maneuvers.

Derived 100% from:
  dead-reckoning-maneuvers.py         — full PID, maneuver logic, WASD keys, CSV logging
  dead-reckoning-optical-position-hold.py — simplified version with same PID
  dead-reckoning-joystick-control.py  — joystick sensitivity, WASD control

Constants from dead-reckoning-maneuvers.py:
  POSITION_KP=1.0, POSITION_KI=0.03, POSITION_KD=0.0
  VELOCITY_KP=0.7, VELOCITY_KI=0.01, VELOCITY_KD=0.0
  MAX_CORRECTION=0.7, VELOCITY_SMOOTHING_ALPHA=0.85
  DRIFT_COMPENSATION_RATE=0.004, PERIODIC_RESET_INTERVAL=90.0
  MOMENTUM_COMPENSATION_TIME=0.10, SETTLING_DURATION=0.1
  JOYSTICK_SENSITIVITY=0.2, DATA_TIMEOUT_THRESHOLD=0.2
  FW_THRUST_BASE=24000, FW_Z_POS_KP=1.6, FW_Z_VEL_KP=15.0
  CRTP_PORT_NEOPIXEL=0x09 (NeoPixel LED feedback)

PID calculation from calculate_position_hold_corrections():
  position_error = -(integrated_pos - target_pos)
  velocity_error = -current_velocity
  correction = pos_P + pos_I + pos_D + vel_P + vel_I + vel_D
  Anti-windup: integral clamped to ±0.1
  MAX_CORRECTION applied as final clamp

Velocity from calculate_velocity():
  velocity_constant = (5.4 * DEG_TO_RAD) / (30.0 * DT)  # test_optical_flow_sensor.py
  velocity = delta * altitude * velocity_constant

Smoothing from smooth_velocity():
  history[1] = history[0]; history[0] = new_velocity
  smoothed = history[0]*ALPHA + history[1]*(1-ALPHA)
  if abs(smoothed) < VELOCITY_THRESHOLD: smoothed = 0.0

Dead-reckoning integrate_position():
  pos += vx * dt
  if velocity_magnitude < VELOCITY_THRESHOLD * 2:
      pos -= pos * DRIFT_COMPENSATION_RATE * dt
  pos = clamp(pos, -MAX_POSITION_ERROR, MAX_POSITION_ERROR)
"""
import time
import math
import threading
import csv
import os
from collections import deque
from datetime import datetime

import pyqtgraph as pg
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                              QLabel, QFrame, QPushButton, QScrollArea,
                              QDoubleSpinBox, QGroupBox, QCheckBox, QSizePolicy,
                              QFileDialog, QLineEdit)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QKeyEvent

from utils.theme import COLORS, card_style, FONT_MONO
from utils.config import (
    POSITION_KP, POSITION_KI, POSITION_KD,
    VELOCITY_KP, VELOCITY_KI, VELOCITY_KD,
    MAX_CORRECTION, VELOCITY_SMOOTHING_ALPHA, VELOCITY_THRESHOLD,
    DRIFT_COMPENSATION_RATE, PERIODIC_RESET_INTERVAL, MAX_POSITION_ERROR,
    CONTROL_UPDATE_RATE, DT, DEG_TO_RAD, OPTICAL_FLOW_FOV_DEG,
    OPTICAL_FLOW_RESOLUTION, MOMENTUM_COMPENSATION_TIME, SETTLING_DURATION,
    SETTLING_CORRECTION_FACTOR, JOYSTICK_SENSITIVITY, MANEUVER_DISTANCE,
    MANEUVER_THRESHOLD, FW_THRUST_BASE, FW_Z_POS_KP, FW_Z_VEL_KP,
    DRONE_CSV_LOGGING, TARGET_HEIGHT, DATA_TIMEOUT_THRESHOLD,
)

HISTORY = 300


class ManeuverPage(QWidget):
    """
    Dead-reckoning position hold + maneuver control page.
    Receives sensor data via push_sensor() from DroneService callbacks.
    Emits correction_ready(vx, vy, height) for the drone to execute.
    """

    # Emitted when PID computes a new correction — controller wires this to drone
    correction_ready      = pyqtSignal(float, float, float)
    # Emitted when APPLY FIRMWARE PARAMS clicked — dict of {param: value_str}
    firmware_params_ready = pyqtSignal(object)
    # Emitted on emergency stop request
    emergency_stop        = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # ── PID state (from dead-reckoning-maneuvers.py global variables) ─────
        self._kp = POSITION_KP
        self._ki = POSITION_KI
        self._kd = POSITION_KD
        self._vkp = VELOCITY_KP
        self._vki = VELOCITY_KI
        self._vkd = VELOCITY_KD
        self._max_corr = MAX_CORRECTION
        self._alpha    = VELOCITY_SMOOTHING_ALPHA

        # Sensor state
        self._current_height  = 0.0
        self._delta_x         = 0
        self._delta_y         = 0
        self._sensor_ready    = False
        self._last_heartbeat  = time.time()

        # Velocity tracking (2-point IIR — smooth_velocity())
        self._vx = 0.0
        self._vy = 0.0
        self._vx_hist = [0.0, 0.0]
        self._vy_hist = [0.0, 0.0]

        # Dead reckoning integration
        self._pos_x  = 0.0
        self._pos_y  = 0.0
        self._last_int_time  = time.time()
        self._last_reset_time = time.time()
        self._integration_enabled = False

        # PID integrals/derivatives
        self._pos_int_x = 0.0; self._pos_int_y = 0.0
        self._pos_deriv_x = 0.0; self._pos_deriv_y = 0.0
        self._last_pos_err_x = 0.0; self._last_pos_err_y = 0.0
        self._vel_int_x = 0.0; self._vel_int_y = 0.0
        self._vel_deriv_x = 0.0; self._vel_deriv_y = 0.0
        self._last_vel_err_x = 0.0; self._last_vel_err_y = 0.0

        # Target position
        self._target_x = 0.0
        self._target_y = 0.0
        self._target_height = TARGET_HEIGHT

        # Maneuver state
        self._maneuver_active = False
        self._waypoints: list = []
        self._waypoint_idx: int = 0

        # Flight state
        self._flight_active = False

        # Joystick command (from WASD keys / buttons)
        self._joy_vx = 0.0
        self._joy_vy = 0.0
        self._joy_active = False

        # CSV logging
        self._csv_enabled = DRONE_CSV_LOGGING
        self._csv_file = None
        self._csv_writer = None
        self._start_time = None

        # History for plots
        self._t_hist   = deque(maxlen=HISTORY)
        self._vx_plot  = deque(maxlen=HISTORY)
        self._vy_plot  = deque(maxlen=HISTORY)
        self._px_plot  = deque(maxlen=HISTORY)
        self._py_plot  = deque(maxlen=HISTORY)
        self._cx_plot  = deque(maxlen=HISTORY)
        self._cy_plot  = deque(maxlen=HISTORY)
        self._h_plot   = deque(maxlen=HISTORY)

        self._data_lock = threading.Lock()
        self._setup_ui()

        # Control loop timer at CONTROL_UPDATE_RATE (50 Hz)
        self._ctrl_timer = QTimer(self)
        self._ctrl_timer.timeout.connect(self._control_tick)
        self._ctrl_timer.start(int(CONTROL_UPDATE_RATE * 1000))

        # Plot refresh at 100ms
        self._plot_timer = QTimer(self)
        self._plot_timer.timeout.connect(self._refresh_plots)
        self._plot_timer.start(100)

    # ── Data input ─────────────────────────────────────────────────────────────

    def push_sensor(self, delta_x: int, delta_y: int, height: float,
                    battery: float = 0.0) -> None:
        """
        Receive motion sensor + height data.
        Matches dead-reckoning-maneuvers.py motion_callback pattern:
          data.get('motion.deltaX', 0), data.get('motion.deltaY', 0)
          data.get('stateEstimate.z', 0.0)
        """
        with self._data_lock:
            self._delta_x = delta_x
            self._delta_y = delta_y
            self._current_height = height
            self._sensor_ready = True
            self._last_heartbeat = time.time()

            # Update battery label if provided
            if battery > 0:
                color = (COLORS['accent_green'] if battery > 3.7
                         else COLORS['accent_amber'] if battery > 3.5
                         else COLORS['accent_red'])
                if hasattr(self, '_lbl_batt'):
                    self._lbl_batt.setText(f"{battery:.2f} V")
                    self._lbl_batt.setStyleSheet(
                        f"color: {color}; font-size: 16px; "
                        f"font-weight: bold; font-family: {FONT_MONO};")

    # ── Build UI ───────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        container.setMinimumSize(1100, 750)
        inner = QVBoxLayout(container)
        inner.setContentsMargins(10, 10, 10, 10)
        inner.setSpacing(8)

        # Title
        title = QLabel("DEAD-RECKONING POSITION HOLD  &  MANEUVERS  (Optical Flow PID)")
        title.setStyleSheet(
            f"color: {COLORS['accent_teal']}; font-size: 14px; font-weight: bold; "
            f"font-family: {FONT_MONO}; letter-spacing: 2px;")
        inner.addWidget(title)

        # Status row
        inner.addWidget(self._build_status_row())

        # Main 3-column layout
        main = QHBoxLayout()
        main.setSpacing(8)
        main.addWidget(self._build_pid_panel(),      stretch=2)
        main.addWidget(self._build_control_panel(),  stretch=2)
        main.addWidget(self._build_plots_panel(),    stretch=3)
        inner.addLayout(main, stretch=1)

        # Firmware params + CSV at bottom
        inner.addWidget(self._build_firmware_panel())

        scroll.setWidget(container)
        root.addWidget(scroll)

    def _build_status_row(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(card_style())
        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(24)

        for label, default, color, attr in [
            ("HEIGHT",     "0.000 m", COLORS['accent_teal'],   "_lbl_height"),
            ("VX",         "0.000",   COLORS['accent_green'],  "_lbl_vx"),
            ("VY",         "0.000",   COLORS['accent_purple'], "_lbl_vy"),
            ("POS X",      "0.000",   COLORS['accent_amber'],  "_lbl_px"),
            ("POS Y",      "0.000",   COLORS['accent_amber'],  "_lbl_py"),
            ("CORR VX",    "0.000",   COLORS['accent_red'],    "_lbl_cvx"),
            ("CORR VY",    "0.000",   COLORS['accent_red'],    "_lbl_cvy"),
            ("BATTERY",    "-- V",    COLORS['accent_green'],  "_lbl_batt"),
            ("PHASE",      "IDLE",    COLORS['accent_purple'], "_lbl_phase"),
            ("SENSOR",     "WAITING", COLORS['text_secondary'],"_lbl_sensor"),
        ]:
            f = QFrame()
            f.setObjectName("status_value_frame")
            fl = QVBoxLayout(f)
            fl.setContentsMargins(6, 4, 6, 4)
            lbl_name = QLabel(label)
            lbl_name.setObjectName("value_small")
            lbl_val = QLabel(default)
            lbl_val.setStyleSheet(
                f"color: {color}; font-size: 15px; font-weight: bold; "
                f"font-family: {FONT_MONO};")
            fl.addWidget(lbl_name)
            fl.addWidget(lbl_val)
            setattr(self, attr, lbl_val)
            layout.addWidget(f)
        layout.addStretch()
        return card

    def _build_pid_panel(self) -> QFrame:
        """PID parameter tuning — from dead-reckoning-maneuvers.py adjustable UI."""
        card = QFrame()
        card.setStyleSheet(card_style())
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        title = QLabel("PID PARAMETERS  (dead-reckoning-maneuvers.py)")
        title.setObjectName("panel_title")
        layout.addWidget(title)

        params = [
            ("Pos KP",  POSITION_KP, 0.0, 5.0,  0.1, "_sp_pkp"),
            ("Pos KI",  POSITION_KI, 0.0, 0.5,  0.01,"_sp_pki"),
            ("Pos KD",  POSITION_KD, 0.0, 1.0,  0.01,"_sp_pkd"),
            ("Vel KP",  VELOCITY_KP, 0.0, 5.0,  0.1, "_sp_vkp"),
            ("Vel KI",  VELOCITY_KI, 0.0, 0.5,  0.01,"_sp_vki"),
            ("Vel KD",  VELOCITY_KD, 0.0, 1.0,  0.01,"_sp_vkd"),
            ("Max Corr",MAX_CORRECTION,0.0,2.0, 0.05,"_sp_maxc"),
            ("Alpha",   VELOCITY_SMOOTHING_ALPHA,0.0,2.0,0.05,"_sp_alpha"),
            ("Height",  TARGET_HEIGHT,0.1,1.5,  0.05,"_sp_height"),
        ]
        grid = QGridLayout()
        grid.setSpacing(4)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 2)
        for i, (label, val, lo, hi, step, attr) in enumerate(params):
            lbl = QLabel(label)
            lbl.setObjectName("value_small")
            sp = QDoubleSpinBox()
            sp.setRange(lo, hi)
            sp.setSingleStep(step)
            sp.setDecimals(3)
            sp.setValue(val)
            sp.valueChanged.connect(self._on_pid_changed)
            setattr(self, attr, sp)
            grid.addWidget(lbl, i, 0)
            grid.addWidget(sp,  i, 1)
        layout.addLayout(grid)

        # Trim controls — from dead-reckoning-maneuvers.py TRIM_VX/VY
        trim_title = QLabel("TRIM  (TRIM_VX / TRIM_VY)")
        trim_title.setObjectName("value_small")
        layout.addWidget(trim_title)
        trim_row = QHBoxLayout()
        from utils.config import TRIM_VX, TRIM_VY
        self._sp_trim_vx = QDoubleSpinBox()
        self._sp_trim_vx.setRange(-0.5, 0.5); self._sp_trim_vx.setSingleStep(0.01)
        self._sp_trim_vx.setValue(TRIM_VX)
        self._sp_trim_vy = QDoubleSpinBox()
        self._sp_trim_vy.setRange(-0.5, 0.5); self._sp_trim_vy.setSingleStep(0.01)
        self._sp_trim_vy.setValue(TRIM_VY)
        # Live-update config when user changes trim spinboxes
        self._sp_trim_vx.valueChanged.connect(self._on_trim_changed)
        self._sp_trim_vy.valueChanged.connect(self._on_trim_changed)
        trim_row.addWidget(QLabel("VX:")); trim_row.addWidget(self._sp_trim_vx)
        trim_row.addWidget(QLabel("VY:")); trim_row.addWidget(self._sp_trim_vy)
        layout.addLayout(trim_row)

        reset_btn = QPushButton("RESET PID STATE")
        reset_btn.clicked.connect(self._reset_pid_state)
        layout.addWidget(reset_btn)
        layout.addStretch()
        return card

    def _build_control_panel(self) -> QFrame:
        """WASD + directional maneuvers — from dead-reckoning-maneuvers.py."""
        card = QFrame()
        card.setStyleSheet(card_style())
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel("MANEUVER CONTROL  (WASD + Directional)")
        title.setObjectName("panel_title")
        layout.addWidget(title)

        # Flight control buttons
        flight_row = QHBoxLayout()
        self._btn_start = QPushButton("START POSITION HOLD")
        self._btn_start.setObjectName("btn_connect")
        self._btn_start.setFixedHeight(36)
        self._btn_start.clicked.connect(self._start_position_hold)

        self._btn_stop = QPushButton("STOP")
        self._btn_stop.setStyleSheet(
            f"background: {COLORS['emergency_red']}; color: white; "
            "font-weight: bold; border-radius: 6px;")
        self._btn_stop.setFixedHeight(36)
        self._btn_stop.clicked.connect(self._stop_flight)

        flight_row.addWidget(self._btn_start)
        flight_row.addWidget(self._btn_stop)
        layout.addLayout(flight_row)

        # ── JOYSTICK WASD (hold to move) — dead-reckoning-maneuvers.py joystick control ──
        joy_grp = QGroupBox("JOYSTICK CONTROL  (WASD - hold to move)")
        joy_grp.setStyleSheet(
            "QGroupBox { color: " + COLORS['text_secondary'] + "; font-size: 11px; "
            "border: 1px solid #444; border-radius: 4px; margin-top: 6px; padding-top: 4px; } "
            "QPushButton#btn_wasd { background-color: " + COLORS['accent_teal'] + "; color: " + COLORS['bg_primary'] + "; font-weight: bold; border-radius: 4px; border: none; } "
            "QPushButton#btn_stop_center { background-color: " + COLORS['emergency_red'] + "; color: white; font-weight: bold; border-radius: 4px; border: none; }")
        joy_layout = QVBoxLayout(joy_grp)
        joy_layout.setContentsMargins(6, 8, 6, 6)
        joy_layout.setSpacing(4)

        # Sensitivity row
        sens_row = QHBoxLayout()
        sens_lbl = QLabel("Sensitivity:")
        sens_lbl.setObjectName("value_small")
        self._sp_joy_sens = QDoubleSpinBox()
        self._sp_joy_sens.setRange(0.1, 2.0)
        self._sp_joy_sens.setSingleStep(0.1)
        self._sp_joy_sens.setValue(JOYSTICK_SENSITIVITY)
        self._sp_joy_sens.setFixedWidth(65)
        sens_hint = QLabel("(0.1–2.0)")
        sens_hint.setObjectName("value_small")
        sens_row.addWidget(sens_lbl)
        sens_row.addWidget(self._sp_joy_sens)
        sens_row.addWidget(sens_hint)
        sens_row.addStretch()
        joy_layout.addLayout(sens_row)

        # WASD d-pad — matches dead-reckoning-maneuvers.py joystick_buttons_frame layout
        # W=forward (+Y), S=backward (-Y), A=left (+X), D=right (-X)
        dpad = QGridLayout()
        dpad.setSpacing(3)
        for _c in range(3): dpad.setColumnStretch(_c, 1)
        for _r in range(3): dpad.setRowStretch(_r, 1)

        # W — forward (+Y in dead-reckoning coords, same as script's joystick W)
        btn_w = QPushButton("↑\nW")
        btn_w.setFixedSize(48, 44)
        btn_w.setObjectName("btn_wasd")
        btn_w.pressed.connect(lambda: self._joy_press(0,  self._sp_joy_sens.value()))
        btn_w.released.connect(self._joy_release)

        # A — left (+X)
        btn_a = QPushButton("←\nA")
        btn_a.setFixedSize(48, 44)
        btn_a.setObjectName("btn_wasd")
        btn_a.pressed.connect(lambda: self._joy_press( self._sp_joy_sens.value(), 0))
        btn_a.released.connect(self._joy_release)

        # STOP (center)
        btn_stop_joy = QPushButton("STOP")
        btn_stop_joy.setFixedSize(48, 44)
        btn_stop_joy.setObjectName("btn_stop_center")
        btn_stop_joy.clicked.connect(self._joy_release)

        # D — right (-X)
        btn_d = QPushButton("→\nD")
        btn_d.setFixedSize(48, 44)
        btn_d.setObjectName("btn_wasd")
        btn_d.pressed.connect(lambda: self._joy_press(-self._sp_joy_sens.value(), 0))
        btn_d.released.connect(self._joy_release)

        # S — backward (-Y)
        btn_s = QPushButton("↓\nS")
        btn_s.setFixedSize(48, 44)
        btn_s.setObjectName("btn_wasd")
        btn_s.pressed.connect(lambda: self._joy_press(0, -self._sp_joy_sens.value()))
        btn_s.released.connect(self._joy_release)

        dpad.addWidget(btn_w,        0, 1, Qt.AlignmentFlag.AlignCenter)
        dpad.addWidget(btn_a,        1, 0, Qt.AlignmentFlag.AlignCenter)
        dpad.addWidget(btn_stop_joy, 1, 1, Qt.AlignmentFlag.AlignCenter)
        dpad.addWidget(btn_d,        1, 2, Qt.AlignmentFlag.AlignCenter)
        dpad.addWidget(btn_s,        2, 1, Qt.AlignmentFlag.AlignCenter)

        joy_outer = QHBoxLayout()
        joy_outer.addStretch()
        joy_outer.addLayout(dpad)
        joy_outer.addStretch()
        joy_layout.addLayout(joy_outer)
        layout.addWidget(joy_grp)

        # ── DIRECTIONAL MANEUVERS — dead-reckoning-maneuvers.py maneuver_forward/backward/left/right ──
        man_grp = QGroupBox("MANEUVER CONTROL  (one-shot move to target)")
        man_grp.setStyleSheet(
            "QGroupBox { color: " + COLORS['text_secondary'] + "; font-size: 11px; "
            "border: 1px solid #444; border-radius: 4px; margin-top: 6px; padding-top: 4px; } "
            "QPushButton#btn_maneuver { background-color: #1a6ea8; color: white; font-weight: bold; border-radius: 4px; border: none; } "
            "QPushButton#btn_stop_center { background-color: " + COLORS['emergency_red'] + "; color: white; font-weight: bold; border-radius: 4px; border: none; } "
            "QPushButton#btn_square { background-color: #7b2fbe; color: white; font-weight: bold; border-radius: 4px; border: none; }")
        man_layout = QVBoxLayout(man_grp)
        man_layout.setContentsMargins(6, 8, 6, 6)
        man_layout.setSpacing(4)

        # Distance entry — matches dead-reckoning-maneuvers.py maneuver_distance_entry
        dist_row = QHBoxLayout()
        dist_lbl = QLabel("Distance (m):")
        dist_lbl.setObjectName("value_small")
        self._sp_man_dist = QDoubleSpinBox()
        self._sp_man_dist.setRange(0.05, 3.0)
        self._sp_man_dist.setSingleStep(0.05)
        self._sp_man_dist.setValue(MANEUVER_DISTANCE)
        self._sp_man_dist.setFixedWidth(70)
        dist_row.addWidget(dist_lbl)
        dist_row.addWidget(self._sp_man_dist)
        dist_row.addStretch()
        man_layout.addLayout(dist_row)

        # Directional grid — matches script layout (Forward top, Backward bottom, Left/Right sides)
        # Script: maneuver_forward → target_y = +dist, maneuver_right → target_x = -dist
        #         maneuver_left   → target_x = +dist, maneuver_backward → target_y = -dist
        man_grid = QGridLayout()
        man_grid.setSpacing(3)
        for _c in range(3): man_grid.setColumnStretch(_c, 1)
        for _r in range(3): man_grid.setRowStretch(_r, 1)

        btn_fwd = QPushButton("↑\nFWD")
        btn_fwd.setFixedSize(56, 44)
        btn_fwd.setObjectName("btn_maneuver")
        btn_fwd.clicked.connect(lambda: self._start_maneuver(0, self._sp_man_dist.value()))

        btn_left = QPushButton("←\nLEFT")
        btn_left.setFixedSize(56, 44)
        btn_left.setObjectName("btn_maneuver")
        btn_left.clicked.connect(lambda: self._start_maneuver( self._sp_man_dist.value(), 0))

        btn_stop_man = QPushButton("STOP")
        btn_stop_man.setFixedSize(56, 44)
        btn_stop_man.setObjectName("btn_stop_center")
        btn_stop_man.clicked.connect(self._stop_maneuver)

        btn_right = QPushButton("→\nRIGHT")
        btn_right.setFixedSize(56, 44)
        btn_right.setObjectName("btn_maneuver")
        btn_right.clicked.connect(lambda: self._start_maneuver(-self._sp_man_dist.value(), 0))

        btn_bwd = QPushButton("↓\nBWD")
        btn_bwd.setFixedSize(56, 44)
        btn_bwd.setObjectName("btn_maneuver")
        btn_bwd.clicked.connect(lambda: self._start_maneuver(0, -self._sp_man_dist.value()))

        man_grid.addWidget(btn_fwd,      0, 1, Qt.AlignmentFlag.AlignCenter)
        man_grid.addWidget(btn_left,     1, 0, Qt.AlignmentFlag.AlignCenter)
        man_grid.addWidget(btn_stop_man, 1, 1, Qt.AlignmentFlag.AlignCenter)
        man_grid.addWidget(btn_right,    1, 2, Qt.AlignmentFlag.AlignCenter)
        man_grid.addWidget(btn_bwd,      2, 1, Qt.AlignmentFlag.AlignCenter)

        man_outer = QHBoxLayout()
        man_outer.addStretch()
        man_outer.addLayout(man_grid)
        man_outer.addStretch()
        man_layout.addLayout(man_outer)

        # Shape buttons row — matches dead-reckoning-maneuvers.py shape_frame
        shapes_row = QHBoxLayout()
        shapes_lbl = QLabel("Shapes:")
        shapes_lbl.setObjectName("value_small")
        btn_square = QPushButton("SQUARE")
        btn_square.setObjectName("btn_square")
        btn_square.setFixedHeight(28)
        btn_square.clicked.connect(self._maneuver_square)
        shapes_row.addWidget(shapes_lbl)
        shapes_row.addWidget(btn_square)
        shapes_row.addStretch()
        man_layout.addLayout(shapes_row)

        layout.addWidget(man_grp)

        # Position reset + Apply buttons — matches dead-reckoning-maneuvers.py apply_all_values / reset
        actions_row = QHBoxLayout()
        reset_pos_btn = QPushButton("RESET ORIGIN")
        reset_pos_btn.setFixedHeight(28)
        reset_pos_btn.clicked.connect(self._reset_position)
        apply_btn = QPushButton("APPLY ALL VALUES")
        apply_btn.setFixedHeight(28)
        apply_btn.setObjectName("btn_apply")
        apply_btn.clicked.connect(self._on_pid_changed)
        reset_def_btn = QPushButton("RESET TO DEFAULT")
        reset_def_btn.setFixedHeight(28)
        reset_def_btn.setObjectName("btn_reset_default")
        reset_def_btn.clicked.connect(self._reset_to_defaults)
        actions_row.addWidget(reset_pos_btn)
        actions_row.addWidget(apply_btn)
        actions_row.addWidget(reset_def_btn)
        layout.addLayout(actions_row)

        # CSV logging toggle
        csv_row = QHBoxLayout()
        self._chk_csv = QCheckBox("CSV Logging")
        self._chk_csv.setChecked(DRONE_CSV_LOGGING)
        self._chk_csv.toggled.connect(self._toggle_csv)
        self._lbl_csv_file = QLabel("No file")
        self._lbl_csv_file.setObjectName("value_small")
        csv_row.addWidget(self._chk_csv)
        csv_row.addWidget(self._lbl_csv_file)
        layout.addLayout(csv_row)

        layout.addStretch()
        return card

    def _build_plots_panel(self) -> QFrame:
        """Velocity + position plots from dead-reckoning-maneuvers.py data visualization."""
        card = QFrame()
        card.setStyleSheet(card_style())
        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        title = QLabel("DEAD RECKONING  —  Velocity · Position · Correction  (50 Hz)")
        title.setObjectName("panel_title")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(4)

        # Velocity plot — Vx (teal), Vy (purple)
        self._vplot = self._make_plot("Velocity  Vx / Vy  (m/s)")
        self._c_vx = self._vplot.plot(pen=pg.mkPen(COLORS['accent_teal'],  width=2), name="Vx")
        self._c_vy = self._vplot.plot(pen=pg.mkPen(COLORS['accent_purple'],width=2), name="Vy")
        grid.addWidget(self._vplot, 0, 0)

        # Position plot — Px (amber), Py (green)
        self._pplot = self._make_plot("Dead-Reckoning Position  X / Y  (m)")
        self._c_px = self._pplot.plot(pen=pg.mkPen(COLORS['accent_amber'], width=2), name="PosX")
        self._c_py = self._pplot.plot(pen=pg.mkPen(COLORS['accent_green'], width=2), name="PosY")
        grid.addWidget(self._pplot, 0, 1)

        # Correction plot — Cx (red), Cy (orange)
        self._cplot = self._make_plot("PID Correction  Cvx / Cvy  (m/s)")
        self._c_cx = self._cplot.plot(pen=pg.mkPen(COLORS['accent_red'],   width=2), name="Cvx")
        self._c_cy = self._cplot.plot(pen=pg.mkPen('#ff8800',              width=2), name="Cvy")
        grid.addWidget(self._cplot, 1, 0)

        # 2D trajectory — from dead-reckoning-maneuvers.py MAX_PLOT_TRAJECTORY_POINTS
        self._traj_plot = pg.PlotWidget(title="2D Trajectory  (dead reckoning)")
        self._traj_plot.setBackground(COLORS['bg_card'])
        self._traj_plot.setAspectLocked(True)
        self._traj_line = self._traj_plot.plot(pen=pg.mkPen(COLORS['accent_teal'], width=2))
        self._traj_dot  = self._traj_plot.plot(
            pen=None, symbol='o', symbolSize=8,
            symbolBrush=COLORS['accent_red'], symbolPen=None)
        grid.addWidget(self._traj_plot, 1, 1)

        grid.setColumnStretch(0, 1); grid.setColumnStretch(1, 1)
        grid.setRowStretch(0, 1);    grid.setRowStretch(1, 1)
        layout.addLayout(grid, stretch=1)
        return card

    def _build_firmware_panel(self) -> QFrame:
        """
        Firmware parameter panel — from dead-reckoning-maneuvers.py apply_firmware_parameters():
          cf.param.set_value('posCtlPid.thrustBase', str(FW_THRUST_BASE))
          cf.param.set_value('posCtlPid.zKp', str(FW_Z_POS_KP))
          cf.param.set_value('velCtlPid.vzKp', str(FW_Z_VEL_KP))
        """
        card = QFrame()
        card.setStyleSheet(card_style())
        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(16)

        title = QLabel("FIRMWARE PARAMS  (posCtlPid.thrustBase · zKp · velCtlPid.vzKp)")
        title.setObjectName("panel_title")
        layout.addWidget(title)

        self._chk_fw = QCheckBox("Apply on Connect")
        self._chk_fw.setChecked(False)
        layout.addWidget(self._chk_fw)

        for label, val, attr in [
            ("thrustBase", FW_THRUST_BASE, "_fw_thrust"),
            ("zKp",        FW_Z_POS_KP,   "_fw_zkp"),
            ("vzKp",       FW_Z_VEL_KP,   "_fw_vzkp"),
        ]:
            lbl = QLabel(label)
            lbl.setObjectName("value_small")
            sp = QDoubleSpinBox()
            sp.setRange(0, 65535)
            sp.setSingleStep(0.1)
            sp.setDecimals(1)
            sp.setValue(val)
            setattr(self, attr, sp)
            layout.addWidget(lbl)
            layout.addWidget(sp)

        self._btn_apply_fw = QPushButton("APPLY FIRMWARE PARAMS")
        self._btn_apply_fw.clicked.connect(self._apply_firmware_params)
        layout.addWidget(self._btn_apply_fw)
        layout.addStretch()
        return card

    def _make_plot(self, title: str) -> pg.PlotWidget:
        pw = pg.PlotWidget(title=title)
        pw.setBackground(COLORS['bg_card'])
        pw.showGrid(x=True, y=True, alpha=0.15)
        pw.getPlotItem().getAxis('left').setTextPen(COLORS['text_secondary'])
        pw.getPlotItem().getAxis('bottom').setTextPen(COLORS['text_secondary'])
        pw.getPlotItem().titleLabel.setAttr('color', COLORS['text_secondary'])
        pw.setMinimumHeight(130)
        return pw

    # ── PID Control Loop (50 Hz) ───────────────────────────────────────────────

    def _control_tick(self) -> None:
        """
        50 Hz control loop.
        Implements calculate_velocity() + smooth_velocity() + integrate_position()
        + calculate_position_hold_corrections() from dead-reckoning-maneuvers.py.
        """
        if not self._flight_active or not self._sensor_ready:
            return

        # Sensor timeout check — DATA_TIMEOUT_THRESHOLD = 0.2s
        if time.time() - self._last_heartbeat > DATA_TIMEOUT_THRESHOLD:
            self._log_status("SENSOR TIMEOUT — hovering in place")
            self.correction_ready.emit(0.0, 0.0, self._target_height)
            return

        with self._data_lock:
            dx = self._delta_x
            dy = self._delta_y
            h  = self._current_height

        now = time.time()
        dt  = min(now - self._last_int_time, 0.1)
        self._last_int_time = now

        # ── calculate_velocity() — test_optical_flow_sensor.py formula ────────
        def _calc_vel(delta, altitude):
            if altitude <= 0:
                return 0.0
            vc = (OPTICAL_FLOW_FOV_DEG * DEG_TO_RAD) / (OPTICAL_FLOW_RESOLUTION * DT)
            return delta * altitude * vc

        raw_vx = _calc_vel(dx, h) + self._sp_trim_vx.value()
        raw_vy = _calc_vel(dy, h) + self._sp_trim_vy.value()

        # ── smooth_velocity() — 2-point IIR from dead-reckoning-maneuvers.py ──
        alpha = self._alpha
        self._vx_hist[1] = self._vx_hist[0]; self._vx_hist[0] = raw_vx
        self._vy_hist[1] = self._vy_hist[0]; self._vy_hist[0] = raw_vy
        svx = self._vx_hist[0] * alpha + self._vx_hist[1] * (1 - alpha)
        svy = self._vy_hist[0] * alpha + self._vy_hist[1] * (1 - alpha)
        self._vx = 0.0 if abs(svx) < VELOCITY_THRESHOLD else svx
        self._vy = 0.0 if abs(svy) < VELOCITY_THRESHOLD else svy

        # ── integrate_position() — trapezoidal + drift compensation ────────────
        vm = math.sqrt(self._vx**2 + self._vy**2)
        self._pos_x += self._vx * dt
        self._pos_y += self._vy * dt
        if vm < VELOCITY_THRESHOLD * 2:
            self._pos_x -= self._pos_x * DRIFT_COMPENSATION_RATE * dt
            self._pos_y -= self._pos_y * DRIFT_COMPENSATION_RATE * dt
        self._pos_x = max(-MAX_POSITION_ERROR, min(MAX_POSITION_ERROR, self._pos_x))
        self._pos_y = max(-MAX_POSITION_ERROR, min(MAX_POSITION_ERROR, self._pos_y))

        # Periodic position reset — PERIODIC_RESET_INTERVAL
        if now - self._last_reset_time >= PERIODIC_RESET_INTERVAL:
            self._reset_position()

        # ── calculate_position_hold_corrections() — full PID ──────────────────
        pos_err_x = -(self._pos_x - self._target_x)
        pos_err_y = -(self._pos_y - self._target_y)
        vel_err_x = -self._vx
        vel_err_y = -self._vy

        # Position PID
        pos_p_x = pos_err_x * self._kp
        pos_p_y = pos_err_y * self._kp
        self._pos_int_x = max(-0.1, min(0.1, self._pos_int_x + pos_err_x * CONTROL_UPDATE_RATE))
        self._pos_int_y = max(-0.1, min(0.1, self._pos_int_y + pos_err_y * CONTROL_UPDATE_RATE))
        pos_i_x = self._pos_int_x * self._ki
        pos_i_y = self._pos_int_y * self._ki
        self._pos_deriv_x = (pos_err_x - self._last_pos_err_x) / CONTROL_UPDATE_RATE
        self._pos_deriv_y = (pos_err_y - self._last_pos_err_y) / CONTROL_UPDATE_RATE
        pos_d_x = self._pos_deriv_x * self._kd
        pos_d_y = self._pos_deriv_y * self._kd
        self._last_pos_err_x = pos_err_x
        self._last_pos_err_y = pos_err_y

        # Velocity PID
        vel_p_x = vel_err_x * self._vkp
        vel_p_y = vel_err_y * self._vkp
        self._vel_int_x = max(-0.1, min(0.1, self._vel_int_x + vel_err_x * CONTROL_UPDATE_RATE))
        self._vel_int_y = max(-0.1, min(0.1, self._vel_int_y + vel_err_y * CONTROL_UPDATE_RATE))
        vel_i_x = self._vel_int_x * self._vki
        vel_i_y = self._vel_int_y * self._vki
        vel_d_x = ((vel_err_x - self._last_vel_err_x) / CONTROL_UPDATE_RATE) * self._vkd
        vel_d_y = ((vel_err_y - self._last_vel_err_y) / CONTROL_UPDATE_RATE) * self._vkd
        self._last_vel_err_x = vel_err_x
        self._last_vel_err_y = vel_err_y

        # Combined correction
        corr_vx = pos_p_x + pos_i_x + pos_d_x + vel_p_x + vel_i_x + vel_d_x
        corr_vy = pos_p_y + pos_i_y + pos_d_y + vel_p_y + vel_i_y + vel_d_y

        # Clamp — MAX_CORRECTION
        mc = self._max_corr
        corr_vx = max(-mc, min(mc, corr_vx))
        corr_vy = max(-mc, min(mc, corr_vy))

        # Add joystick input (hold mode: add to PID output)
        final_vx = corr_vx + self._joy_vx
        final_vy = corr_vy + self._joy_vy

        self.correction_ready.emit(final_vx, final_vy, self._target_height)

        # ── Waypoint progression (square / multi-point maneuver) ──────────────
        # Matches dead-reckoning-maneuvers.py: if within MANEUVER_THRESHOLD, advance
        if self._maneuver_active and self._waypoints:
            dist_to_target = math.sqrt(
                (self._pos_x - self._target_x)**2 +
                (self._pos_y - self._target_y)**2
            )
            if dist_to_target < MANEUVER_THRESHOLD:
                self._waypoint_idx += 1
                if self._waypoint_idx < len(self._waypoints):
                    self._target_x, self._target_y = self._waypoints[self._waypoint_idx]
                    self._log_status(f"Waypoint {self._waypoint_idx}/{len(self._waypoints)}: "
                                     f"({self._target_x:.2f}, {self._target_y:.2f})")
                else:
                    # All waypoints done — hold at final position
                    self._waypoints = []
                    self._waypoint_idx = 0
                    self._maneuver_active = False
                    self._set_phase("HOVER" if self._flight_active else "IDLE")
                    self._log_status("Shape maneuver complete — holding")

        # History for plots + CSV
        t = now - (self._start_time or now)
        with self._data_lock:
            self._t_hist.append(t)
            self._vx_plot.append(self._vx)
            self._vy_plot.append(self._vy)
            self._px_plot.append(self._pos_x)
            self._py_plot.append(self._pos_y)
            self._cx_plot.append(corr_vx)
            self._cy_plot.append(corr_vy)
            self._h_plot.append(h)

        # CSV logging — from dead-reckoning-maneuvers.py DRONE_CSV_LOGGING
        if self._csv_enabled and self._csv_writer:
            try:
                self._csv_writer.writerow([
                    f"{t:.3f}", f"{h:.4f}",
                    f"{dx}", f"{dy}",
                    f"{self._vx:.4f}", f"{self._vy:.4f}",
                    f"{self._pos_x:.4f}", f"{self._pos_y:.4f}",
                    f"{corr_vx:.4f}", f"{corr_vy:.4f}",
                ])
            except Exception:
                pass

        # Update status labels
        self._lbl_height.setText(f"{h:.3f} m")
        self._lbl_vx.setText(f"{self._vx:.3f}")
        self._lbl_vy.setText(f"{self._vy:.3f}")
        self._lbl_px.setText(f"{self._pos_x:.3f}")
        self._lbl_py.setText(f"{self._pos_y:.3f}")
        self._lbl_cvx.setText(f"{corr_vx:.3f}")
        self._lbl_cvy.setText(f"{corr_vy:.3f}")
        sensor_ok = (time.time() - self._last_heartbeat) < DATA_TIMEOUT_THRESHOLD
        self._lbl_sensor.setText("OK" if sensor_ok else "TIMEOUT")
        self._lbl_sensor.setStyleSheet(
            f"color: {COLORS['accent_green'] if sensor_ok else COLORS['accent_red']}; "
            f"font-size: 15px; font-weight: bold; font-family: {FONT_MONO};")

    def _refresh_plots(self) -> None:
        """Update pyqtgraph plots from history."""
        with self._data_lock:
            t  = list(self._t_hist)
            vx = list(self._vx_plot); vy = list(self._vy_plot)
            px = list(self._px_plot); py = list(self._py_plot)
            cx = list(self._cx_plot); cy = list(self._cy_plot)

        if not t:
            return
        self._c_vx.setData(t, vx); self._c_vy.setData(t, vy)
        self._c_px.setData(t, px); self._c_py.setData(t, py)
        self._c_cx.setData(t, cx); self._c_cy.setData(t, cy)
        # 2D trajectory
        self._traj_line.setData(px, py)
        if px:
            self._traj_dot.setData([px[-1]], [py[-1]])

    # ── Handlers ───────────────────────────────────────────────────────────────

    def _on_trim_changed(self) -> None:
        """Live-update TRIM values in config when spinboxes change."""
        import utils.config as _cfg
        _cfg.TRIM_VX = self._sp_trim_vx.value()
        _cfg.TRIM_VY = self._sp_trim_vy.value()

    def _on_pid_changed(self) -> None:
        self._kp     = self._sp_pkp.value()
        self._ki     = self._sp_pki.value()
        self._kd     = self._sp_pkd.value()
        self._vkp    = self._sp_vkp.value()
        self._vki    = self._sp_vki.value()
        self._vkd    = self._sp_vkd.value()
        self._max_corr = self._sp_maxc.value()
        self._alpha    = self._sp_alpha.value()
        self._target_height = self._sp_height.value()

    def _start_position_hold(self) -> None:
        self._reset_pid_state()
        self._flight_active = True
        self._start_time = time.time()
        if self._csv_enabled:
            self._open_csv()
        self._set_phase("HOVER")
        self._log_status("Position hold ACTIVE")

    def _stop_flight(self) -> None:
        self._flight_active = False
        self._joy_vx = 0.0; self._joy_vy = 0.0
        self._maneuver_active = False
        self._close_csv()
        self.correction_ready.emit(0.0, 0.0, self._target_height)
        self._set_phase("IDLE")
        self._log_status("Flight STOPPED")

    def _set_phase(self, phase: str) -> None:
        """Update the PHASE display — matches dead-reckoning-maneuvers.py flight_phase variable."""
        if hasattr(self, '_lbl_phase'):
            colors = {
                "IDLE":    COLORS['text_secondary'],
                "TAKEOFF": COLORS['accent_amber'],
                "HOVER":   COLORS['accent_teal'],
                "MANEUVER":COLORS['accent_purple'],
                "LANDING": COLORS['accent_red'],
            }
            c = colors.get(phase, COLORS['text_secondary'])
            self._lbl_phase.setText(phase)
            self._lbl_phase.setStyleSheet(
                f"color: {c}; font-size: 15px; font-weight: bold; font-family: {FONT_MONO};")

    def _joy_press(self, vx: float, vy: float) -> None:
        self._joy_vx = vx; self._joy_vy = vy; self._joy_active = True

    def _joy_release(self) -> None:
        # Momentum compensation from dead-reckoning-maneuvers.py
        self._joy_vx = 0.0; self._joy_vy = 0.0; self._joy_active = False

    def _start_maneuver(self, dx: float, dy: float) -> None:
        """
        Set a new target position offset — dead-reckoning-maneuvers.py pattern:
          reset_position_tracking(reset_integrals=False)  # keep learned trim
          new_target_x = 0.0; new_target_y = distance   (forward example)
        We reset pos to 0 here to match the script's approach of measuring from current spot.
        """
        # Reset position to zero (current spot = new origin), keep integrals (learned drift)
        self._pos_x = 0.0; self._pos_y = 0.0
        self._last_int_time = time.time()
        self._target_x = dx
        self._target_y = dy
        self._maneuver_active = True
        self._set_phase("MANEUVER")
        self._log_status(f"Maneuver → ({dx:+.2f}, {dy:+.2f}) m")

    def _stop_maneuver(self) -> None:
        """Stop current maneuver — matches dead-reckoning-maneuvers.py stop_maneuver()."""
        self._maneuver_active = False
        self._target_x = self._pos_x
        self._target_y = self._pos_y
        self._set_phase("HOVER" if self._flight_active else "IDLE")
        self._log_status("Maneuver stopped — holding position")

    def _maneuver_square(self) -> None:
        """
        Square shape — matches dead-reckoning-maneuvers.py maneuver_square() waypoints:
          (-dist, 0), (-dist, dist), (0, dist), (0, 0)
        Simplified: sequence handled via _waypoints list.
        """
        dist = self._sp_man_dist.value()
        # Reset to current position as origin (keep integrals)
        self._pos_x = 0.0; self._pos_y = 0.0
        self._last_int_time = time.time()
        # Store waypoints — processed in _control_tick when maneuver reaches each
        self._waypoints = [
            (-dist, 0.0),
            (-dist,  dist),
            (0.0,    dist),
            (0.0,    0.0),
        ]
        self._waypoint_idx = 0
        if self._waypoints:
            self._target_x, self._target_y = self._waypoints[0]
        self._maneuver_active = True
        self._set_phase("MANEUVER")
        self._log_status(f"Square maneuver {dist:.2f}m initiated")

    def _reset_to_defaults(self) -> None:
        """Reset all PID parameters to script defaults — dead-reckoning-maneuvers.py constants."""
        self._sp_pkp.setValue(POSITION_KP)
        self._sp_pki.setValue(POSITION_KI)
        self._sp_pkd.setValue(POSITION_KD)
        self._sp_vkp.setValue(VELOCITY_KP)
        self._sp_vki.setValue(VELOCITY_KI)
        self._sp_vkd.setValue(VELOCITY_KD)
        self._sp_maxc.setValue(MAX_CORRECTION)
        self._sp_alpha.setValue(VELOCITY_SMOOTHING_ALPHA)
        self._sp_height.setValue(TARGET_HEIGHT)
        self._on_pid_changed()
        self._log_status("Parameters reset to defaults")

    def _reset_position(self) -> None:
        """reset_position_tracking() from dead-reckoning-maneuvers.py."""
        self._pos_x = 0.0; self._pos_y = 0.0
        self._target_x = 0.0; self._target_y = 0.0
        self._last_reset_time = time.time()
        self._last_int_time = time.time()

    def _reset_pid_state(self) -> None:
        """Full PID reset — same as dead-reckoning-maneuvers.py reset_position_tracking(reset_integrals=True)."""
        self._reset_position()
        self._pos_int_x = 0.0; self._pos_int_y = 0.0
        self._vel_int_x = 0.0; self._vel_int_y = 0.0
        self._last_pos_err_x = 0.0; self._last_pos_err_y = 0.0
        self._last_vel_err_x = 0.0; self._last_vel_err_y = 0.0
        self._pos_x = 0.0; self._pos_y = 0.0
        self._vx = 0.0; self._vy = 0.0
        self._vx_hist = [0.0, 0.0]; self._vy_hist = [0.0, 0.0]
        self._integration_enabled = True

    def _apply_firmware_params(self) -> None:
        """
        Apply firmware PID parameters — dead-reckoning-maneuvers.py apply_firmware_parameters():
          cf.param.set_value('posCtlPid.thrustBase', str(FW_THRUST_BASE))
          cf.param.set_value('posCtlPid.zKp', str(FW_Z_POS_KP))
          cf.param.set_value('velCtlPid.vzKp', str(FW_Z_VEL_KP))
        Emits signal so controller can call on live cf object.
        """
        self._fw_params = {
            'posCtlPid.thrustBase': str(int(self._fw_thrust.value())),
            'posCtlPid.zKp':        str(self._fw_zkp.value()),
            'velCtlPid.vzKp':       str(self._fw_vzkp.value()),
        }
        self.firmware_params_ready.emit(self._fw_params)
        self._log_status(
            f"Firmware: thrustBase={int(self._fw_thrust.value())} "
            f"zKp={self._fw_zkp.value()} vzKp={self._fw_vzkp.value()}")

    def get_firmware_params(self) -> dict:
        """Return firmware params dict for controller to apply via cf.param.set_value."""
        return getattr(self, '_fw_params', {})

    # ── CSV Logging ────────────────────────────────────────────────────────────

    def _toggle_csv(self, enabled: bool) -> None:
        self._csv_enabled = enabled
        if not enabled:
            self._close_csv()

    def _open_csv(self) -> None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(os.getcwd(), f"flight_log_{ts}.csv")
        try:
            self._csv_file = open(path, 'w', newline='')
            self._csv_writer = csv.writer(self._csv_file)
            self._csv_writer.writerow([
                "time_s", "height_m",
                "deltaX", "deltaY",
                "vx_ms", "vy_ms",
                "pos_x_m", "pos_y_m",
                "corr_vx", "corr_vy",
            ])
            self._lbl_csv_file.setText(os.path.basename(path))
        except Exception as e:
            self._lbl_csv_file.setText(f"Error: {e}")

    def _close_csv(self) -> None:
        if self._csv_file:
            try:
                self._csv_file.close()
            except Exception:
                pass
            self._csv_file = None
            self._csv_writer = None

    def _log_status(self, msg: str) -> None:
        """Log to console (controller can also redirect to connect page log)."""
        print(f"[ManeuverPage] {msg}")
