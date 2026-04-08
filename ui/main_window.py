"""
MainWindow — NanoHawk Control Station.

Multi-page app with top navigation bar.
Pages (QStackedWidget):
  0. CONNECT      — drone connection, battery, ToF, TOC browser, safety unlock
  1. FLIGHT       — live camera, map, tracking, telemetry, drone control, mission
  2. ANALYTICS    — optical flow (EMA), 2D position tracker, full telemetry graphs
  3. IMU          — roll/pitch/yaw live plots + 3D attitude widget (from test_imu.py)
  4. SECURITY     — HMAC audit log, stats, replay/range counters

demo_mode=True  → simulated data so UI can be tested without hardware.
demo_mode=False → real services via connect_services(controller).
                  Panels show "Connect Drone First" until drone is live.
"""
import time

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QStackedWidget,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from utils.theme import (COLORS, get_main_stylesheet, get_light_stylesheet,
                         apply_light_mode, apply_dark_mode, FONT_MONO)
from ui.pages.connect_page   import ConnectPage
from ui.pages.flight_page    import FlightPage
from ui.pages.analytics_page import AnalyticsPage
from ui.pages.imu_page       import ImuPage
from ui.pages.security_page  import SecurityPage
from ui.pages.maneuver_page  import ManeuverPage
from ui.widgets.toast        import ToastNotification


_NAV_PAGES = [
    ("⚡  CONNECT",   "Connection & Diagnostics"),
    ("✈  FLIGHT",    "Live Flight Dashboard"),
    ("📊  ANALYTICS", "Sensor Graphs & Position"),
    ("🧭  IMU",       "Attitude & Acceleration"),
    ("🔒  SECURITY",  "HMAC Audit & Events"),
    ("🎯  MANEUVER",  "Dead-Reckoning Position Hold & Maneuvers"),
]


class MainWindow(QMainWindow):
    """
    Root window with top nav bar and 5 pages.
    demo_mode=True: animated dashboard with no hardware.
    demo_mode=False: wire real services via connect_services(controller).
    """

    def __init__(self, demo_mode: bool = False):
        super().__init__()
        self._demo_mode = demo_mode
        self._dark_mode = False   # default: light/white theme
        self._connected = False
        apply_light_mode()        # patch COLORS dict before any widget is built
        self._setup_window()
        self._build_ui()
        if demo_mode:
            self._start_demo()

    # ── Window ────────────────────────────────────────────────────────────────

    def _setup_window(self) -> None:
        self.setWindowTitle("NanoHawk Control Station  |  Edge AI Drone Dashboard")
        self.setMinimumSize(1300, 780)
        self.resize(1600, 960)
        # Default: light theme
        self.setStyleSheet(get_light_stylesheet())

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._topbar = self._build_topbar()
        root.addWidget(self._topbar)
        root.addWidget(self._build_navbar())
        root.addWidget(self._build_stack(), stretch=1)

    # ── Top bar ───────────────────────────────────────────────────────────────

    def _build_topbar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(50)
        bar.setStyleSheet(
            f"background: {COLORS['header_bg']}; "
            f"border-bottom: 1px solid {COLORS['border']};")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 4, 16, 4)

        brand = QLabel("⬡  NANOHAWK  CONTROL  STATION")
        brand.setStyleSheet(
            f"color: {COLORS['accent_teal']}; font-size: 17px; font-weight: bold; "
            f"font-family: {FONT_MONO}; letter-spacing: 3px;")
        layout.addWidget(brand)

        sub = QLabel("Secure Vision-Based Human Tracking  ·  Edge AI  ·  CRTP over UDP")
        sub.setObjectName("value_small")
        sub.setStyleSheet(f"color: {COLORS['text_secondary']}; margin-left: 14px;")
        layout.addWidget(sub)
        layout.addStretch()

        self._global_status = QLabel("● SYSTEM READY")
        self._global_status.setStyleSheet(
            f"color: {COLORS['accent_green']}; font-weight: bold; "
            f"font-family: {FONT_MONO};")
        layout.addWidget(self._global_status)
        layout.addSpacing(20)

        self._clock_lbl = QLabel("--:--:--")
        self._clock_lbl.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-family: {FONT_MONO}; font-size: 13px;")
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._tick_clock)
        self._clock_timer.start(1000)
        self._tick_clock()
        layout.addWidget(self._clock_lbl)
        layout.addSpacing(14)

        self._theme_btn = QPushButton("🌙 DARK")
        self._theme_btn.setFixedSize(80, 32)
        self._theme_btn.clicked.connect(self._toggle_theme)
        layout.addWidget(self._theme_btn)
        layout.addSpacing(8)

        emg = QPushButton("⚠  EMERGENCY STOP")
        emg.setObjectName("btn_emergency")
        emg.setFixedHeight(36)
        emg.clicked.connect(self._on_emergency)
        layout.addWidget(emg)

        return bar

    # ── Nav bar ───────────────────────────────────────────────────────────────

    def _build_navbar(self) -> QFrame:
        nav = QFrame()
        nav.setFixedHeight(44)
        nav.setStyleSheet(
            f"background: {COLORS['bg_card']}; "
            f"border-bottom: 2px solid {COLORS['accent_teal']};")
        self._navbar_frame = nav   # store ref for theme refresh
        layout = QHBoxLayout(nav)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(4)

        self._nav_btns: list[QPushButton] = []
        for i, (label, tooltip) in enumerate(_NAV_PAGES):
            btn = QPushButton(label)
            btn.setToolTip(tooltip)
            btn.setFixedHeight(40)
            btn.setCheckable(True)
            btn.setChecked(i == 0)
            btn.setStyleSheet(self._nav_btn_style(i == 0))
            btn.clicked.connect(lambda checked, idx=i: self._switch_page(idx))
            self._nav_btns.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        self._conn_badge = QLabel("○ DISCONNECTED")
        self._conn_badge.setStyleSheet(
            f"color: {COLORS['accent_red']}; font-family: {FONT_MONO}; "
            "font-size: 12px; font-weight: bold; padding: 0 10px;")
        layout.addWidget(self._conn_badge)

        return nav

    def _nav_btn_style(self, active: bool) -> str:
        if active:
            return (
                f"background: {COLORS['accent_teal']}; color: {COLORS['bg_primary']}; "
                "font-weight: bold; border-radius: 6px; font-size: 13px; padding: 0 14px;")
        return (
            f"background: transparent; color: {COLORS['text_secondary']}; "
            "font-weight: bold; border-radius: 6px; font-size: 13px; padding: 0 14px;")

    def _switch_page(self, idx: int) -> None:
        self._stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._nav_btns):
            btn.setChecked(i == idx)
            btn.setStyleSheet(self._nav_btn_style(i == idx))

    # ── Stacked pages ─────────────────────────────────────────────────────────

    def _build_stack(self) -> QStackedWidget:
        self._stack = QStackedWidget()

        # Page 0 — Connect
        self.connect_page = ConnectPage()
        self._stack.addWidget(self.connect_page)

        # Page 1 — Flight
        self.flight_page = FlightPage()
        self.camera_panel    = self.flight_page.camera_panel
        self.map_panel       = self.flight_page.map_panel
        self.tracking_panel  = self.flight_page.tracking_panel
        self.telemetry_panel = self.flight_page.telemetry_panel
        self.drone_panel     = self.flight_page.drone_panel
        self.mission_panel   = self.flight_page.mission_panel
        self.system_panel    = self.flight_page.system_panel
        self._stack.addWidget(self.flight_page)

        # Page 2 — Analytics
        self.analytics_page = AnalyticsPage()
        self.flow_panel      = self.analytics_page.flow_panel
        self.position_panel  = self.analytics_page.position_panel
        self._stack.addWidget(self.analytics_page)

        # Page 3 — IMU (from test_imu.py)
        self.imu_page = ImuPage()
        self._stack.addWidget(self.imu_page)

        # Page 4 — Security
        self.security_page  = SecurityPage()
        self.security_panel = self.security_page.security_panel
        self._stack.addWidget(self.security_page)

        # Page 5 — Maneuver (dead-reckoning PID from dead-reckoning-maneuvers.py)
        self.maneuver_page = ManeuverPage()
        self._stack.addWidget(self.maneuver_page)

        return self._stack

    # ── Header helpers ────────────────────────────────────────────────────────

    def _tick_clock(self) -> None:
        self._clock_lbl.setText(time.strftime("%H:%M:%S"))

    def _on_emergency(self) -> None:
        # Update UI immediately
        self._global_status.setText("● EMERGENCY STOP ACTIVATED")
        self._global_status.setStyleSheet(
            f"color: {COLORS['accent_red']}; font-weight: bold; font-family: {FONT_MONO};")
        self._conn_badge.setText("⚠ EMERGENCY STOP")
        self._conn_badge.setStyleSheet(
            f"color: {COLORS['accent_red']}; font-family: {FONT_MONO}; "
            "font-size: 12px; font-weight: bold; padding: 0 10px;")
        # Cut drone thrust — route through stored controller reference
        if hasattr(self, '_controller') and self._controller is not None:
            self._controller.drone.emergency_stop()
        self.connect_page._log("⚠ EMERGENCY STOP — thrust cut!", color="#ff4444")

    def _toggle_theme(self) -> None:
        self._dark_mode = not self._dark_mode
        if self._dark_mode:
            apply_dark_mode()
            self.setStyleSheet(get_main_stylesheet())
            self._theme_btn.setText("☀ LIGHT")
        else:
            apply_light_mode()
            self.setStyleSheet(get_light_stylesheet())
            self._theme_btn.setText("🌙 DARK")
        # Re-apply all inline styles that use COLORS (topbar, navbar, labels)
        self._refresh_inline_styles()
        # Refresh card frame backgrounds
        self._refresh_all_card_styles()

    def _refresh_inline_styles(self) -> None:
        """Re-apply inline setStyleSheet calls that reference COLORS after theme switch."""
        # Topbar background
        self._topbar.setStyleSheet(
            f"background: {COLORS['header_bg']}; "
            f"border-bottom: 1px solid {COLORS['border']};")
        # Brand / subtitle labels in topbar
        for widget in self._topbar.findChildren(QLabel):
            txt = widget.text()
            if "NANOHAWK" in txt:
                widget.setStyleSheet(
                    f"color: {COLORS['accent_teal']}; font-size: 17px; font-weight: bold; "
                    f"font-family: {FONT_MONO}; letter-spacing: 3px;")
            elif "Secure Vision" in txt:
                widget.setStyleSheet(
                    f"color: {COLORS['text_secondary']}; margin-left: 14px;")
            elif "SYSTEM" in txt or "DRONE" in txt or "EMERGENCY" in txt:
                # Keep global_status color intact (only update bg/font)
                pass
        # Clock
        self._clock_lbl.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-family: {FONT_MONO}; font-size: 13px;")
        # Navbar background + conn badge
        self._navbar_frame.setStyleSheet(
            f"background: {COLORS['bg_card']}; "
            f"border-bottom: 2px solid {COLORS['accent_teal']};")
        self._conn_badge.setStyleSheet(
            f"color: {COLORS['accent_red'] if '○' in self._conn_badge.text() or '⚠' in self._conn_badge.text() else COLORS['accent_green']}; "
            f"font-family: {FONT_MONO}; font-size: 12px; font-weight: bold; padding: 0 10px;")
        # Refresh nav button styles
        for i, btn in enumerate(self._nav_btns):
            btn.setStyleSheet(self._nav_btn_style(btn.isChecked()))

    def _refresh_all_card_styles(self) -> None:
        """Walk all QFrame children and re-apply card_style() so cards match current theme."""
        from PyQt6.QtWidgets import QFrame
        from utils.theme import card_style
        for frame in self.findChildren(QFrame):
            existing = frame.styleSheet()
            # Only re-style frames that are card containers (have border-radius:12px)
            # Skip topbar/navbar (fixed height frames) and frames with no card style
            if "border-radius: 12px" in existing and frame not in (self._topbar, self._navbar_frame):
                frame.setStyleSheet(card_style())

    # ── Connection badge ──────────────────────────────────────────────────────

    def set_connected(self, connected: bool) -> None:
        self._connected = connected
        if connected:
            self._conn_badge.setText("● CONNECTED")
            self._conn_badge.setStyleSheet(
                f"color: {COLORS['accent_green']}; font-family: {FONT_MONO}; "
                "font-size: 12px; font-weight: bold; padding: 0 10px;")
            self._global_status.setText("● DRONE ONLINE")
            self._global_status.setStyleSheet(
                f"color: {COLORS['accent_green']}; font-weight: bold; "
                f"font-family: {FONT_MONO};")
            # connect_page.on_connected() is called directly by controller signal
        else:
            self._conn_badge.setText("○ DISCONNECTED")
            self._conn_badge.setStyleSheet(
                f"color: {COLORS['accent_red']}; font-family: {FONT_MONO}; "
                "font-size: 12px; font-weight: bold; padding: 0 10px;")
            # connect_page.on_disconnected() is called directly by controller signal
            # Show toast notification + play alert
            self._show_disconnect_toast()

    def _show_disconnect_toast(self) -> None:
        """Show toast notification and play audio on drone disconnect."""
        toast = ToastNotification(
            self,
            title="Drone Disconnected",
            message="Connection to NanoHawk lost.\nReturn to CONNECT page to reconnect.",
            level="error",
        )
        toast.show_toast()
        # Audio alert (Windows winsound, silent fail on other platforms)
        try:
            import winsound
            winsound.Beep(880, 200)
            winsound.Beep(660, 200)
            winsound.Beep(440, 400)
        except Exception:
            pass

    # ── Service wiring (Plan B) ───────────────────────────────────────────────

    def connect_services(self, controller) -> None:
        """Called from main.py to wire real services."""
        if self._demo_mode:
            if hasattr(self, '_demo_timer'):
                self._demo_timer.stop()
            self._demo_mode = False
        self._controller = controller   # stored so _on_emergency can call drone.emergency_stop()
        controller.connect_to_window(self)

    # ── Demo mode (hardware-free testing only) ─────────────────────────────────

    def _start_demo(self) -> None:
        import math, random
        from models.drone_state import DroneState
        from models.tracking_data import TrackingData
        from models.security_event import SecurityEvent

        self._demo_t = 0.0
        self._demo_event_counter = 0
        self._demo_timer = QTimer(self)

        def _tick():
            self._demo_t += 0.1
            t = self._demo_t
            state = DroneState(
                connected=True,
                battery_voltage=3.7 + 0.1 * math.sin(t * 0.1),
                battery_percent=60.0 + 10.0 * math.sin(t * 0.05),
                pitch=5.0 * math.sin(t * 0.7),
                roll=3.0 * math.cos(t * 0.5),
                yaw=(t * 10) % 360,
                height=0.4 + 0.05 * math.sin(t),
                motor_m1=22000 + int(2000 * math.sin(t)),
                motor_m2=21000 + int(2000 * math.cos(t)),
                motor_m3=23000 + int(1500 * math.sin(t + 1)),
                motor_m4=22000 + int(1500 * math.cos(t + 1)),
                velocity_x=0.2 * math.sin(t * 0.3),
                velocity_y=0.15 * math.cos(t * 0.4),
                delta_x=3.5 * math.sin(t * 0.8) + random.gauss(0, 0.3),
                delta_y=2.8 * math.cos(t * 0.6) + random.gauss(0, 0.3),
            )
            self.telemetry_panel.set_state(state)
            self.map_panel.set_state(state)
            self.drone_panel.set_connected(True)
            self.analytics_page.set_state(state)
            self.connect_page.set_battery(state.battery_voltage)
            self.connect_page.set_height(state.height)

            # IMU page demo
            self.imu_page.push_imu(
                state.roll, state.pitch, state.yaw,
                math.sin(t * 0.5) * 0.3,
                math.cos(t * 0.4) * 0.2,
                9.81 + math.sin(t * 0.1) * 0.05,
            )

            # Maneuver page demo — feed optical flow delta + height + battery
            self.maneuver_page.push_sensor(
                state.delta_x * 0.01,   # raw pixel delta (small values)
                state.delta_y * 0.01,
                state.height,
                state.battery_voltage,
            )

            detected = (t % 10) < 7
            tracking = TrackingData(
                person_detected=detected,
                bbox=(100, 80, 220, 280),
                center_x=160 + int(80 * math.sin(t * 0.2)),
                center_y=120 + int(40 * math.cos(t * 0.3)),
                confidence=0.87 + 0.05 * math.sin(t),
                distance_estimate=2.5 + 0.5 * math.sin(t * 0.15),
                frame_fps=28.5 + random.uniform(-1, 1),
                cmd_vx=0.3 * math.sin(t * 0.2),
                cmd_vy=0.2 * math.cos(t * 0.3),
            )
            self.tracking_panel.set_tracking(tracking)
            self.camera_panel.set_fps(tracking.frame_fps)
            self.camera_panel.set_detection(tracking.person_detected, tracking.confidence)
            self.mission_panel.set_target_locked(tracking.person_detected)
            self.system_panel.set_stats(
                cpu=30.0 + 10.0 * math.sin(t * 0.2),
                ram=40.0 + 5.0 * math.cos(t * 0.1),
                latency_ms=12.0 + 5.0 * abs(math.sin(t * 0.3)),
            )
            self.system_panel.set_fps(tracking.frame_fps)
            motion = 1.0 if abs(state.delta_x) > 0.5 or abs(state.delta_y) > 0.5 else 0.0
            self.flow_panel.set_flow(state.delta_x, state.delta_y, motion, state.height)

            self._demo_event_counter += 1
            if self._demo_event_counter % 30 == 0:
                from models.security_event import SecurityEvent
                self.security_panel.add_event(SecurityEvent(
                    event_type="VALID", timestamp=time.time(), verdict="ALLOWED",
                    token_valid=True,
                    details=f"vx={state.velocity_x:.2f} vy={state.velocity_y:.2f}",
                ))
            if self._demo_event_counter % 137 == 0:
                self.security_panel.add_event(SecurityEvent(
                    event_type="REPLAY_ATTACK", timestamp=time.time(), verdict="DROPPED",
                    token_valid=False, details="nonce reused within 5s window",
                ))
            if self._demo_event_counter % 89 == 0:
                self.security_panel.add_event(SecurityEvent(
                    event_type="INVALID_RANGE", timestamp=time.time(), verdict="DROPPED",
                    token_valid=True, details="vx=0.95 exceeds MAX_SPEED=0.4",
                ))

        self._demo_timer.timeout.connect(_tick)
        self._demo_timer.start(100)
