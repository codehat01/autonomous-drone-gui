"""
MainController — wires all Plan B services to the UI panels.

Called from main.py when DEMO_MODE = False:
    controller = MainController()
    window.connect_services(controller)   # UI calls controller.connect_to_window()
    controller.start_all()
    app.aboutToQuit.connect(controller.stop_all)

Service graph:
    CameraService  ──frame──►  YoloService  ──tracking──►  SecurityService
                                                                │
                                                    command_accepted
                                                                │
                                                         DroneService.send_command()
    DroneService   ──state──►  UI panels (telemetry, map)
    SystemMonitor  ──stats──►  SystemPanel
    SecurityService ──event──►  SecurityPanel
"""
from PyQt6.QtCore import QObject, pyqtSlot

from services.camera_service import CameraService
from services.yolo_service import YoloService
from services.drone_service import DroneService
from services.system_monitor import SystemMonitor
from services.security_service import SecurityService
from utils.config import TARGET_HEIGHT


class MainController(QObject):
    """
    Owns all service objects and manages their lifecycle.
    Provides connect_to_window(window) to wire signals to UI slots.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.camera   = CameraService()
        self.yolo     = YoloService()
        self.drone    = DroneService()
        self.monitor  = SystemMonitor()
        self.security = SecurityService()

        self._target_height = TARGET_HEIGHT
        self._auto_mode = False

        # Internal wiring: camera → yolo, yolo → security → drone
        self.camera.frame_ready.connect(self.yolo.push_frame)
        self.yolo.tracking_ready.connect(self._on_tracking)
        self.security.command_accepted.connect(self._on_command_accepted)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start_all(self) -> None:
        # NOTE: drone is NOT started here — user must click CONNECT on the Connect page.
        # This prevents the drone service from spamming connection errors on startup.
        self.camera.start()
        self.yolo.start()
        self.monitor.start()

    def stop_all(self) -> None:
        self.camera.stop()
        self.yolo.stop()
        self.drone.stop()
        self.monitor.stop()

    # ── Window wiring ─────────────────────────────────────────────────────────

    def connect_to_window(self, window) -> None:
        """
        Wire service signals → UI panel slots.
        window is the MainWindow instance.
        """
        # ── Camera panel ──────────────────────────────────────────────────────
        self.camera.fps_updated.connect(window.camera_panel.set_fps)
        self.camera.source_changed.connect(
            lambda src: window.camera_panel.set_fps(0.0))  # reset on switch
        self.yolo.annotated_frame.connect(window.camera_panel.set_frame)

        # ── Tracking panel ────────────────────────────────────────────────────
        self.yolo.tracking_ready.connect(window.tracking_panel.set_tracking)
        self.yolo.tracking_ready.connect(
            lambda td: window.camera_panel.set_detection(
                td.person_detected, td.confidence))
        self.yolo.tracking_ready.connect(
            lambda td: window.mission_panel.set_target_locked(td.person_detected))

        # ── Telemetry + map panels ────────────────────────────────────────────
        self.drone.state_updated.connect(window.telemetry_panel.set_state)
        self.drone.state_updated.connect(window.map_panel.set_state)

        # ── Position panel — velocity from drone state ────────────────────────
        self.drone.state_updated.connect(
            lambda s: window.position_panel.set_velocity(s.velocity_x, s.velocity_y))

        # ── Flow panel — optical flow data from drone state ───────────────────
        # motion.deltaX/Y come in DroneState.delta_x/y; motion flag from velocity magnitude
        self.drone.state_updated.connect(
            lambda s: window.flow_panel.set_flow(
                s.delta_x, s.delta_y,
                1.0 if (abs(s.velocity_x) > 0.005 or abs(s.velocity_y) > 0.005) else 0.0,
                s.height,
            )
        )

        # ── Analytics page — all cflib_groundStation telemetry graphs ───────────
        self.drone.state_updated.connect(window.analytics_page.set_state)

        # ── IMU page — roll/pitch/yaw/ax/ay/az (from test_imu.py pattern) ───────
        self.drone.imu_updated.connect(window.imu_page.push_imu)

        # ── Maneuver page — optical flow delta + height + battery ─────────────
        # delta_x/y are raw optical flow pixel deltas; height and battery from state
        self.drone.state_updated.connect(
            lambda s: window.maneuver_page.push_sensor(
                s.delta_x, s.delta_y, s.height, s.battery_voltage))

        # Maneuver page PID correction output → security pipeline → drone
        window.maneuver_page.correction_ready.connect(
            lambda vx, vy, h: self.security.submit_command(vx, vy, h))

        # Firmware params → cf.param.set_value (dead-reckoning-maneuvers.py apply_firmware_parameters)
        window.maneuver_page.firmware_params_ready.connect(
            self._on_firmware_params)

        # Maneuver page emergency stop → drone (redundant path alongside drone_panel button)
        window.maneuver_page.emergency_stop.connect(self.drone.emergency_stop)
        window.maneuver_page.emergency_stop.connect(window._on_emergency)

        # ── Sensor timeout — DATA_TIMEOUT_THRESHOLD=0.2s (dead-reckoning-maneuvers.py)
        self.drone.sensor_timeout.connect(
            lambda timed_out: window.connect_page.on_error(
                "SENSOR TIMEOUT — no data for 0.2s" if timed_out else "Sensor resumed"))

        # ── Drone connection status ───────────────────────────────────────────
        self.drone.connected.connect(lambda: window.drone_panel.set_connected(True))
        self.drone.connected.connect(lambda: window.set_connected(True))
        self.drone.connected.connect(window.connect_page.on_connected)
        self.drone.disconnected.connect(lambda: window.drone_panel.set_connected(False))
        self.drone.disconnected.connect(lambda: window.set_connected(False))
        self.drone.disconnected.connect(window.connect_page.on_disconnected)
        self.drone.disconnected.connect(window.telemetry_panel.clear_state)
        self.drone.disconnected.connect(window.analytics_page.clear_state)
        self.drone.error_occurred.connect(window.connect_page._log)

        # ── Connect page — battery + ToF live readouts ────────────────────────
        self.drone.state_updated.connect(
            lambda s: window.connect_page.set_battery(s.battery_voltage))
        self.drone.state_updated.connect(
            lambda s: window.connect_page.set_height(s.height))

        self.drone.state_updated.connect(window.analytics_page.set_state)

        # ── Connect page signals → drone service ──────────────────────────────
        window.connect_page.connect_requested.connect(
            lambda uri: self._on_connect_page_connect(uri))
        window.connect_page.disconnect_requested.connect(self.drone.stop)
        window.connect_page.arm_requested.connect(self._on_arm_requested)
        window.connect_page.high_level_requested.connect(self._on_high_level_requested)
        window.connect_page.neopixel_requested.connect(self._on_neopixel)

        # ── System panel ──────────────────────────────────────────────────────
        self.monitor.stats_updated.connect(window.system_panel.set_stats)
        self.camera.fps_updated.connect(window.system_panel.set_fps)

        # ── Security panel ────────────────────────────────────────────────────
        self.security.event_emitted.connect(window.security_panel.add_event)
        self.security.command_accepted.connect(
            lambda *_: window.security_panel.add_event)  # counter bump via signal

        # ── Mission panel counter updates ──────────────────────────────────
        self.security.command_accepted.connect(self._bump_mission_counter)
        self.security.command_blocked.connect(self._bump_blocked_counter)
        self._window = window

        # ── UI → controller (drone panel buttons) ─────────────────────────────
        window.drone_panel.emergency_stop_requested.connect(self.drone.emergency_stop)
        window.drone_panel.emergency_stop_requested.connect(
            lambda: window._on_emergency())
        window.drone_panel.mode_changed.connect(self._on_mode_changed)
        window.drone_panel.manual_command.connect(self._on_manual_command)
        window.drone_panel.connect_requested.connect(self.drone.start)
        window.drone_panel.disconnect_requested.connect(self.drone.stop)

        # ── Mission quick actions ─────────────────────────────────────────────
        window.mission_panel.takeoff_requested.connect(self._on_takeoff)
        window.mission_panel.hover_requested.connect(self._on_hover)
        window.mission_panel.land_requested.connect(self._on_land)

    # ── Connect page handlers ─────────────────────────────────────────────────

    def _on_connect_page_connect(self, uri: str) -> None:
        """
        Start (or restart) drone service with the URI typed by the user.
        Re-wires all signals so the new DroneService instance feeds the UI.
        """
        self.drone.stop()
        from services.drone_service import DroneService
        self.drone = DroneService(uri=uri)

        # Re-wire drone signals to window (window reference stored in connect_to_window)
        if hasattr(self, '_window'):
            w = self._window
            self.drone.state_updated.connect(w.telemetry_panel.set_state)
            self.drone.state_updated.connect(w.map_panel.set_state)
            self.drone.state_updated.connect(
                lambda s: w.position_panel.set_velocity(s.velocity_x, s.velocity_y))
            self.drone.state_updated.connect(
                lambda s: w.flow_panel.set_flow(
                    s.delta_x, s.delta_y,
                    1.0 if (abs(s.velocity_x) > 0.005 or abs(s.velocity_y) > 0.005) else 0.0,
                    s.height))
            self.drone.state_updated.connect(w.analytics_page.set_state)
            self.drone.state_updated.connect(
                lambda s: w.connect_page.set_battery(s.battery_voltage))
            self.drone.state_updated.connect(
                lambda s: w.connect_page.set_height(s.height))
            self.drone.imu_updated.connect(w.imu_page.push_imu)
            self.drone.state_updated.connect(
                lambda s: w.maneuver_page.push_sensor(
                    s.delta_x, s.delta_y, s.height, s.battery_voltage))
            w.maneuver_page.correction_ready.connect(
                lambda vx, vy, h: self.security.submit_command(vx, vy, h))
            w.maneuver_page.firmware_params_ready.connect(self._on_firmware_params)
            w.maneuver_page.emergency_stop.connect(self.drone.emergency_stop)
            w.maneuver_page.emergency_stop.connect(w._on_emergency)
            self.drone.connected.connect(lambda: w.drone_panel.set_connected(True))
            self.drone.connected.connect(lambda: w.set_connected(True))
            self.drone.connected.connect(w.connect_page.on_connected)
            self.drone.disconnected.connect(lambda: w.drone_panel.set_connected(False))
            self.drone.disconnected.connect(lambda: w.set_connected(False))
            self.drone.disconnected.connect(w.connect_page.on_disconnected)
            self.drone.error_occurred.connect(w.connect_page._log)

        self.security.command_accepted.connect(self._on_command_accepted)
        self.drone.start()

    def _on_arm_requested(self) -> None:
        """Safety unlock — send_setpoint(0,0,0,0) matching hellow_litewing.py."""
        if hasattr(self.drone, '_cf') and self.drone._cf is not None:
            try:
                self.drone._cf.commander.send_setpoint(0, 0, 0, 0)
            except Exception as e:
                pass

    def _on_high_level_requested(self, enable: bool) -> None:
        """Set commander.enHighLevel — matching zrange_read.py / height-hold-joystick.py."""
        if hasattr(self.drone, '_cf') and self.drone._cf is not None:
            try:
                self.drone._cf.param.set_value(
                    'commander.enHighLevel', '1' if enable else '0')
            except Exception:
                pass

    # ── Command routing ───────────────────────────────────────────────────────

    @pyqtSlot(object)
    def _on_tracking(self, tracking_data) -> None:
        """In AUTO mode: pass YOLO velocity commands through security pipeline."""
        if not self._auto_mode:
            return
        self.security.submit_command(
            tracking_data.cmd_vx,
            tracking_data.cmd_vy,
            self._target_height,
        )

    @pyqtSlot(float, float, float)
    def _on_command_accepted(self, vx: float, vy: float, height: float) -> None:
        self.drone.send_command(vx, vy, height)

    @pyqtSlot(float, float, float)
    def _on_manual_command(self, vx: float, vy: float, height: float) -> None:
        """Manual D-pad command — bypasses YOLO but still through security."""
        self.security.submit_command(vx, vy, height)

    @pyqtSlot(str)
    def _on_mode_changed(self, mode: str) -> None:
        self._auto_mode = (mode == "AUTO TRACK")
        if hasattr(self, "_window"):
            self._window.mission_panel.set_mode(mode)

    def _on_takeoff(self) -> None:
        # Use graduated takeoff sequence from auto-take-off script
        self.drone.request_takeoff(TARGET_HEIGHT)
        self.security.submit_command(0.0, 0.0, TARGET_HEIGHT)

    def _on_hover(self) -> None:
        self.security.submit_command(0.0, 0.0, self._target_height)

    def _on_land(self) -> None:
        # Use graduated landing sequence (reverse of takeoff)
        self.drone.request_land()
        self.security.submit_command(0.0, 0.0, 0.0)

    # ── Mission counter helpers ───────────────────────────────────────────────

    def _bump_mission_counter(self, *_) -> None:
        if hasattr(self, "_window"):
            self._window.mission_panel.set_command_counts(
                self.security.sent_count,
                self.security.blocked_count,
            )

    def _bump_blocked_counter(self, *_) -> None:
        self._bump_mission_counter()

    @pyqtSlot(str, int, int, int)
    def _on_neopixel(self, action: str, r: int, g: int, b: int) -> None:
        """
        Route NeoPixel commands to DroneService.
        Actions match dead-reckoning-maneuvers.py np_* helpers:
            set_all      → neopixel_set_all(r, g, b) + neopixel_show()
            clear        → neopixel_clear()
            blink_start  → neopixel_blink(500, 500, start=True)
            blink_stop   → neopixel_blink(start=False)
        """
        if action == "set_all":
            self.drone.neopixel_set_all(r, g, b)
            self.drone.neopixel_show()
        elif action == "clear":
            self.drone.neopixel_clear()
        elif action == "blink_start":
            self.drone.neopixel_blink(500, 500, start=True)
        elif action == "blink_stop":
            self.drone.neopixel_blink(start=False)

    @pyqtSlot(object)
    def _on_firmware_params(self, params: dict) -> None:
        """
        Apply firmware PID params to live drone.
        Matches dead-reckoning-maneuvers.py apply_firmware_parameters():
            cf.param.set_value('posCtlPid.thrustBase', str(FW_THRUST_BASE))
            cf.param.set_value('posCtlPid.zKp',        str(FW_Z_POS_KP))
            cf.param.set_value('velCtlPid.vzKp',       str(FW_Z_VEL_KP))
        """
        if not hasattr(self.drone, '_cf') or self.drone._cf is None:
            return
        for param_name, value_str in params.items():
            try:
                self.drone._cf.param.set_value(param_name, value_str)
            except Exception:
                pass
