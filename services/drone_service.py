"""
DroneService — QThread wrapping cflib for NanoHawk / Crazyflie communication.

Patterns directly match the Python-Scripts implementations:
  - cflib_groundStation.py    (LogConfig, SyncCrazyflie, data_received_cb)
  - vx-vy-calculation-from-flow-and-tof.py  (motion.deltaX/Y, stateEstimate.z)
  - dead-reckoning-position-hold.py  (send_hover_setpoint, safety unlock)

Architecture:
  - Connection runs inside the QThread so cflib's internal threads don't
    block the Qt main thread.
  - Telemetry callbacks post data back to Qt via signals (thread-safe).
  - A watchdog timer sends hover-hold if no command arrives within 500ms.
  - Emergency stop cuts thrust immediately via send_stop_setpoint().

Emits:
    state_updated(DroneState)    — 10ms telemetry loop (100Hz, SENSOR_PERIOD_MS from scripts)
    connected()                  — on successful link-up
    disconnected()               — on link loss or stop()
    error_occurred(str)          — any connection / logging error
"""
import time
import threading
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from models.drone_state import DroneState
from utils.config import (
    DRONE_URI, TARGET_HEIGHT, MAX_SPEED, TELEMETRY_PERIOD_MS,
    DATA_TIMEOUT_THRESHOLD,
)

try:
    import cflib.crtp
    from cflib.crazyflie import Crazyflie
    from cflib.crazyflie.log import LogConfig
    from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
    _HAS_CFLIB = True
except ImportError:
    _HAS_CFLIB = False


class DroneService(QThread):
    """
    Manages the full lifecycle of a Crazyflie drone connection.

    Typical usage:
        svc = DroneService()
        svc.state_updated.connect(panel.set_state)
        svc.start()              # begins connection attempt
        svc.send_command(vx, vy, height)
        svc.emergency_stop()
        svc.stop()
    """

    state_updated   = pyqtSignal(object)   # DroneState
    imu_updated     = pyqtSignal(float, float, float, float, float, float)  # roll,pitch,yaw,ax,ay,az
    sensor_timeout  = pyqtSignal(bool)    # True = timed out, False = resumed
    connected       = pyqtSignal()
    disconnected    = pyqtSignal()
    error_occurred  = pyqtSignal(str)

    # Watchdog: if no command in this many seconds → hover in place
    WATCHDOG_TIMEOUT = 0.5
    # Time to stabilise after arm unlock
    ARM_SETTLE_S = 0.2

    def __init__(self, uri: str = DRONE_URI, parent=None):
        super().__init__(parent)
        self._uri = uri
        self._running = False
        self._cf: Optional[object] = None        # Crazyflie instance
        self._scf: Optional[object] = None       # SyncCrazyflie context

        # Latest telemetry (written by cflib callback, read by watchdog)
        self._state = DroneState()
        self._state_lock = threading.Lock()

        # Pending velocity command
        self._cmd_vx = 0.0
        self._cmd_vy = 0.0
        self._cmd_height = TARGET_HEIGHT
        self._cmd_lock = threading.Lock()
        self._last_cmd_time = 0.0

        self._emergency = False
        self._armed = False
        self._takeoff_requested = False
        self._takeoff_height = TARGET_HEIGHT
        self._land_requested = False

        # Sensor heartbeat — DATA_TIMEOUT_THRESHOLD=0.2s from dead-reckoning-maneuvers.py
        self._last_sensor_time = time.monotonic()
        self._sensor_timed_out = False

    # ── Public API ────────────────────────────────────────────────────────────

    # ── NeoPixel LED control (dead-reckoning-maneuvers.py _send_crtp_with_fallback) ──

    def _send_crtp_with_fallback(self, port: int, channel: int, payload: bytes) -> None:
        """
        Robust CRTP send — exact copy of dead-reckoning-maneuvers.py pattern.
        Tries cf.send_packet, then _link/link.sendPacket, then cflib.crtp.send_packet.
        """
        if self._cf is None:
            return

        header = ((port & 0x0F) << 4) | (channel & 0x0F)

        class _Pkt:
            def __init__(self, h, d):
                self.header = h
                self.data = d
                try:    self.datat = tuple(d)
                except: self.datat = ()
            def is_data_size_valid(self): return len(self.data) <= 30
            @property
            def size(self): return len(self.data)
            def raw(self): return bytes([self.header]) + self.data

        pkt = _Pkt(header, payload)
        cf = self._cf

        try:
            fn = getattr(cf, "send_packet", None)
            if callable(fn):
                fn(pkt); return
        except Exception:
            pass

        try:
            link = getattr(cf, "_link", None) or getattr(cf, "link", None)
            if link is not None:
                for attr in ("sendPacket", "send_packet"):
                    m = getattr(link, attr, None)
                    if callable(m):
                        try: m(pkt); return
                        except Exception: pass
        except Exception:
            pass

        try:
            import cflib.crtp as _crtp
            sp = getattr(_crtp, "send_packet", None)
            if callable(sp):
                try: sp(pkt); return
                except Exception:
                    try: sp(pkt.raw()); return
                    except Exception: pass
        except Exception:
            pass

    def neopixel_set_pixel(self, index: int, r: int, g: int, b: int) -> None:
        """np_set_pixel — CRTP port 0x09 channel SET_PIXEL (0x00)."""
        from utils.config import CRTP_PORT_NEOPIXEL, NEOPIXEL_CHANNEL_SET_PIXEL
        self._send_crtp_with_fallback(
            CRTP_PORT_NEOPIXEL, NEOPIXEL_CHANNEL_SET_PIXEL,
            bytes([index & 0xFF, r & 0xFF, g & 0xFF, b & 0xFF]))

    def neopixel_set_all(self, r: int, g: int, b: int) -> None:
        """np_set_all — broadcast index 0xFF to set all pixels at once."""
        from utils.config import CRTP_PORT_NEOPIXEL, NEOPIXEL_CHANNEL_SET_PIXEL
        self._send_crtp_with_fallback(
            CRTP_PORT_NEOPIXEL, NEOPIXEL_CHANNEL_SET_PIXEL,
            bytes([0xFF, r & 0xFF, g & 0xFF, b & 0xFF]))

    def neopixel_show(self) -> None:
        """np_show — latch pixel data to LEDs."""
        from utils.config import CRTP_PORT_NEOPIXEL, NEOPIXEL_CHANNEL_SHOW
        self._send_crtp_with_fallback(CRTP_PORT_NEOPIXEL, NEOPIXEL_CHANNEL_SHOW, b"")

    def neopixel_clear(self) -> None:
        """np_clear — turn all LEDs off."""
        from utils.config import CRTP_PORT_NEOPIXEL, NEOPIXEL_CHANNEL_CLEAR
        self._send_crtp_with_fallback(CRTP_PORT_NEOPIXEL, NEOPIXEL_CHANNEL_CLEAR, b"")

    def neopixel_blink(self, on_ms: int = 500, off_ms: int = 500, start: bool = True) -> None:
        """np_start_blink / np_stop_blink."""
        from utils.config import CRTP_PORT_NEOPIXEL, NEOPIXEL_CHANNEL_BLINK
        if start:
            data = bytes([1, (on_ms >> 8) & 0xFF, on_ms & 0xFF,
                             (off_ms >> 8) & 0xFF, off_ms & 0xFF])
        else:
            data = bytes([0, 0, 0, 0, 0])
        self._send_crtp_with_fallback(CRTP_PORT_NEOPIXEL, NEOPIXEL_CHANNEL_BLINK, data)

    def send_command(self, vx: float, vy: float, height: float) -> None:
        """Thread-safe command update. Applied on next control tick."""
        with self._cmd_lock:
            self._cmd_vx = max(-MAX_SPEED, min(MAX_SPEED, vx))
            self._cmd_vy = max(-MAX_SPEED, min(MAX_SPEED, vy))
            self._cmd_height = height
            self._last_cmd_time = time.monotonic()

    def emergency_stop(self) -> None:
        """Immediately cut thrust. Sends stop 3× for UDP reliability. Must reconnect to resume."""
        self._emergency = True
        if self._cf is not None:
            for _ in range(3):
                try:
                    self._cf.commander.send_stop_setpoint()
                except Exception:
                    pass
                time.sleep(0.02)

    def request_takeoff(self, target_height: float = TARGET_HEIGHT) -> None:
        """
        Request graduated takeoff sequence.
        From auto-take-off-with-height-hold-joystick-control.py:
            steps = 5; for i in range(steps): height = (i+1)*TARGET/steps
        """
        self._takeoff_requested = True
        self._takeoff_height = target_height

    def request_land(self) -> None:
        """Request graduated landing sequence (reverse of takeoff)."""
        self._land_requested = True

    def stop(self) -> None:
        self._running = False
        self.wait()

    # ── QThread entry point ───────────────────────────────────────────────────

    @staticmethod
    def _normalise_uri(uri: str) -> str:
        """
        Ensure the URI has a port number.
        udpdriver.py crashes with TypeError when parse.port is None.
        Drone hotspot uses port 2390 (udpdriver.py hardcodes this).
        """
        uri = uri.strip()
        if uri.startswith("udp://"):
            host_part = uri[6:]   # everything after udp://
            if ":" not in host_part:
                uri = uri + ":2390"
        return uri

    def run(self) -> None:
        if not _HAS_CFLIB:
            self.error_occurred.emit("cflib not installed — drone service unavailable")
            return

        self._running = True
        # init_drivers() must be called once — matches dead-reckoning-maneuvers.py main()
        try:
            cflib.crtp.init_drivers()
        except Exception as e:
            self.error_occurred.emit(f"cflib init warning: {e}")

        # Normalise URI — guarantee port present (udpdriver.py requires it)
        self._uri = self._normalise_uri(self._uri)
        self.error_occurred.emit(f"Connecting to {self._uri}…")

        while self._running and not self._emergency:
            try:
                self._connect_and_fly()
            except Exception as e:
                self.error_occurred.emit(f"Connection error: {e}")
                self.disconnected.emit()
                if self._running and not self._emergency:
                    time.sleep(3.0)   # retry after 3s

    # ── Connection & flight loop ──────────────────────────────────────────────

    def _connect_and_fly(self) -> None:
        self._cf = Crazyflie(rw_cache="./cache")

        # Wire connection callbacks for live status feedback
        self._cf.connected.add_callback(self._cb_connected)
        self._cf.disconnected.add_callback(self._cb_disconnected)
        self._cf.connection_failed.add_callback(self._cb_connection_failed)
        self._cf.connection_lost.add_callback(self._cb_connection_lost)

        with SyncCrazyflie(self._uri, cf=self._cf) as scf:
            self._armed = False
            self._emergency = False

            # Safety unlock — matches cflib_groundStation.py / hellow_litewing.py
            self._cf.commander.send_setpoint(0, 0, 0, 0)
            time.sleep(self.ARM_SETTLE_S)
            self._armed = True

            # Set up telemetry logging — matches cflib_groundStation.py LogConfig pattern
            self._setup_logging()

            # Control loop at 50 Hz
            while self._running and not self._emergency:
                # Graduated takeoff sequence — auto-take-off-with-height-hold script
                if self._takeoff_requested:
                    self._takeoff_requested = False
                    self._graduated_takeoff(self._takeoff_height)
                # Graduated landing sequence (reverse of takeoff)
                if self._land_requested:
                    self._land_requested = False
                    self._graduated_land()

                self._control_tick()
                time.sleep(0.02)   # 50 Hz

            # Safe shutdown
            try:
                self._cf.commander.send_stop_setpoint()
            except Exception:
                pass
            self._stop_logging()
        self.disconnected.emit()

    def _graduated_takeoff(self, target_height: float) -> None:
        """
        Graduated takeoff — matches dead-reckoning-position-hold.py:
            cf.commander.send_hover_setpoint(TRIM_VX, TRIM_VY, 0, TARGET_HEIGHT)
        Uses TRIM corrections during takeoff for straight lift-off.
        """
        from utils.config import TRIM_VX, TRIM_VY
        # Ramp height from 0 to target in TAKEOFF_TIME seconds at 50Hz
        steps = 50  # 1 second at 50Hz
        for i in range(steps):
            if self._emergency or not self._running:
                return
            h = (i + 1) * target_height / steps
            try:
                self._cf.commander.send_hover_setpoint(TRIM_VX, TRIM_VY, 0, h)
            except Exception:
                return
            time.sleep(0.02)  # 50Hz
        # Update cruise height
        with self._cmd_lock:
            self._cmd_height = target_height

    def _graduated_land(self) -> None:
        """
        Graduated landing — reverse of takeoff (from auto-take-off script).
            for i in range(steps):
                height = TAKEOFF_HEIGHT * (steps - i - 1) / steps
        """
        steps = 5
        with self._cmd_lock:
            current_h = self._cmd_height
        for i in range(steps):
            if self._emergency or not self._running:
                return
            h = current_h * (steps - i - 1) / steps
            try:
                self._cf.commander.send_hover_setpoint(0, 0, 0, h)
            except Exception:
                return
            time.sleep(0.15)
        try:
            self._cf.commander.send_stop_setpoint()
        except Exception:
            pass

    def _control_tick(self) -> None:
        """Send a hover setpoint every 20ms. Watchdog zeros cmd if stale."""
        now = time.monotonic()

        # Sensor heartbeat check — DATA_TIMEOUT_THRESHOLD=0.2s (dead-reckoning-maneuvers.py)
        sensor_age = now - self._last_sensor_time
        timed_out = sensor_age > DATA_TIMEOUT_THRESHOLD
        if timed_out != self._sensor_timed_out:
            self._sensor_timed_out = timed_out
            self.sensor_timeout.emit(timed_out)

        with self._cmd_lock:
            age = now - self._last_cmd_time
            if age > self.WATCHDOG_TIMEOUT:
                cmd_vx, cmd_vy, height = 0.0, 0.0, self._cmd_height
            else:
                cmd_vx, cmd_vy, height = self._cmd_vx, self._cmd_vy, self._cmd_height

        # Axis swap + TRIM — matches dead-reckoning-position-hold.py exactly:
        #   total_vx = TRIM_VX + motion_vy  (note: vy correction goes to vx axis)
        #   total_vy = TRIM_VY + motion_vx  (note: vx correction goes to vy axis)
        from utils.config import TRIM_VX, TRIM_VY
        vx = TRIM_VX + cmd_vy
        vy = TRIM_VY + cmd_vx

        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            try:
                self._cf.commander.send_hover_setpoint(vx, vy, 0.0, height)
            except Exception as e:
                self.error_occurred.emit(f"Command send error: {e}")

    # ── LogConfig setup — matches cflib_groundStation.py exactly ─────────────

    def _setup_logging(self) -> None:
        period = TELEMETRY_PERIOD_MS   # 10ms = 100Hz (SENSOR_PERIOD_MS from all scripts)

        self._log_imu = LogConfig(name="IMU", period_in_ms=period)
        self._log_imu.add_variable("stateEstimate.pitch", "float")
        self._log_imu.add_variable("stateEstimate.roll",  "float")
        self._log_imu.add_variable("stateEstimate.yaw",   "float")
        self._log_imu.add_variable("stateEstimate.z",     "float")
        self._log_imu.data_received_cb.add_callback(self._cb_imu)

        # Dedicated IMU+accel logs for ImuPage (from test_imu.py LOG_PERIOD_MS=50)
        # Split into two LogConfigs (3 floats each = 12 bytes) to stay within
        # CRTP packet size limit. 50ms period matches test_imu.py exactly.
        IMU_PERIOD_MS = 50
        toc = self._cf.log.toc.toc

        self._log_imu_orient = LogConfig(name="IMUOrient", period_in_ms=IMU_PERIOD_MS)
        for full_name, var_type in [("stateEstimate.roll", "float"),
                                     ("stateEstimate.pitch", "float"),
                                     ("stateEstimate.yaw", "float")]:
            group, name = full_name.split(".", maxsplit=1)
            if group in toc and name in toc[group]:
                self._log_imu_orient.add_variable(full_name, var_type)
        self._log_imu_orient.data_received_cb.add_callback(self._cb_imu_orient)

        self._log_imu_accel = LogConfig(name="IMUAccel", period_in_ms=IMU_PERIOD_MS)
        for full_name, var_type in [("stateEstimate.ax", "float"),
                                     ("stateEstimate.ay", "float"),
                                     ("stateEstimate.az", "float")]:
            group, name = full_name.split(".", maxsplit=1)
            if group in toc and name in toc[group]:
                self._log_imu_accel.add_variable(full_name, var_type)
        self._log_imu_accel.data_received_cb.add_callback(self._cb_imu_accel)

        self._log_battery = LogConfig(name="Battery", period_in_ms=period)
        self._log_battery.add_variable("pm.vbat",      "float")
        self._log_battery.add_variable("pm.batteryLevel", "uint8_t")
        self._log_battery.data_received_cb.add_callback(self._cb_battery)

        self._log_motors = LogConfig(name="Motors", period_in_ms=period)
        self._log_motors.add_variable("pwm.m1_pwm", "uint32_t")
        self._log_motors.add_variable("pwm.m2_pwm", "uint32_t")
        self._log_motors.add_variable("pwm.m3_pwm", "uint32_t")
        self._log_motors.add_variable("pwm.m4_pwm", "uint32_t")
        self._log_motors.data_received_cb.add_callback(self._cb_motors)

        self._log_flow = LogConfig(name="Flow", period_in_ms=period)
        self._log_flow.add_variable("motion.deltaX", "int16_t")
        self._log_flow.add_variable("motion.deltaY", "int16_t")
        # velocity.x/y from stateEstimator (m/s)
        self._log_flow.add_variable("stateEstimate.vx", "float")
        self._log_flow.add_variable("stateEstimate.vy", "float")
        self._log_flow.data_received_cb.add_callback(self._cb_flow)

        for lc in [self._log_imu, self._log_imu_orient, self._log_imu_accel,
                   self._log_battery, self._log_motors, self._log_flow]:
            if not lc.variables:
                continue   # skip empty configs (TOC check found nothing)
            try:
                self._cf.log.add_config(lc)
                lc.start()
            except Exception as e:
                self.error_occurred.emit(f"LogConfig error ({lc.name}): {e}")

    def _stop_logging(self) -> None:
        for attr in ("_log_imu", "_log_imu_orient", "_log_imu_accel",
                     "_log_battery", "_log_motors", "_log_flow"):
            lc = getattr(self, attr, None)
            if lc is not None:
                try:
                    lc.stop()
                except Exception:
                    pass

    # ── Telemetry callbacks (called from cflib thread) ────────────────────────

    def _cb_imu(self, timestamp, data, logconf) -> None:
        self._last_sensor_time = time.monotonic()   # heartbeat
        with self._state_lock:
            self._state = DroneState(
                connected=True,
                battery_voltage=self._state.battery_voltage,
                battery_percent=self._state.battery_percent,
                pitch=data.get("stateEstimate.pitch", 0.0),
                roll=data.get("stateEstimate.roll",  0.0),
                yaw=data.get("stateEstimate.yaw",   0.0),
                height=data.get("stateEstimate.z",   0.0),
                motor_m1=self._state.motor_m1,
                motor_m2=self._state.motor_m2,
                motor_m3=self._state.motor_m3,
                motor_m4=self._state.motor_m4,
                velocity_x=self._state.velocity_x,
                velocity_y=self._state.velocity_y,
                delta_x=self._state.delta_x,
                delta_y=self._state.delta_y,
            )
        self.state_updated.emit(self._state)

    def _cb_battery(self, timestamp, data, logconf) -> None:
        with self._state_lock:
            self._state = DroneState(
                connected=True,
                battery_voltage=data.get("pm.vbat", 0.0),
                battery_percent=float(data.get("pm.batteryLevel", 0)),
                pitch=self._state.pitch,
                roll=self._state.roll,
                yaw=self._state.yaw,
                height=self._state.height,
                motor_m1=self._state.motor_m1,
                motor_m2=self._state.motor_m2,
                motor_m3=self._state.motor_m3,
                motor_m4=self._state.motor_m4,
                velocity_x=self._state.velocity_x,
                velocity_y=self._state.velocity_y,
                delta_x=self._state.delta_x,
                delta_y=self._state.delta_y,
            )

    def _cb_motors(self, timestamp, data, logconf) -> None:
        with self._state_lock:
            self._state = DroneState(
                connected=self._state.connected,
                battery_voltage=self._state.battery_voltage,
                battery_percent=self._state.battery_percent,
                pitch=self._state.pitch,
                roll=self._state.roll,
                yaw=self._state.yaw,
                height=self._state.height,
                motor_m1=data.get("pwm.m1_pwm", 0),
                motor_m2=data.get("pwm.m2_pwm", 0),
                motor_m3=data.get("pwm.m3_pwm", 0),
                motor_m4=data.get("pwm.m4_pwm", 0),
                velocity_x=self._state.velocity_x,
                velocity_y=self._state.velocity_y,
                delta_x=self._state.delta_x,
                delta_y=self._state.delta_y,
            )

    def _cb_flow(self, timestamp, data, logconf) -> None:
        with self._state_lock:
            self._state = DroneState(
                connected=self._state.connected,
                battery_voltage=self._state.battery_voltage,
                battery_percent=self._state.battery_percent,
                pitch=self._state.pitch,
                roll=self._state.roll,
                yaw=self._state.yaw,
                height=self._state.height,
                motor_m1=self._state.motor_m1,
                motor_m2=self._state.motor_m2,
                motor_m3=self._state.motor_m3,
                motor_m4=self._state.motor_m4,
                velocity_x=data.get("stateEstimate.vx", 0.0),
                velocity_y=data.get("stateEstimate.vy", 0.0),
                delta_x=data.get("motion.deltaX", 0),
                delta_y=data.get("motion.deltaY", 0),
            )

    # Latest cached orientation/accel for merging the two split LogConfigs
    _imu_roll: float  = 0.0
    _imu_pitch: float = 0.0
    _imu_yaw: float   = 0.0
    _imu_ax: float    = 0.0
    _imu_ay: float    = 0.0
    _imu_az: float    = 0.0

    def _cb_imu_orient(self, timestamp, data, logconf) -> None:
        """Receive orientation packet and emit imu_updated (test_imu.py pattern)."""
        self._imu_roll  = data.get("stateEstimate.roll",  0.0)
        self._imu_pitch = data.get("stateEstimate.pitch", 0.0)
        self._imu_yaw   = data.get("stateEstimate.yaw",   0.0)
        self.imu_updated.emit(
            self._imu_roll, self._imu_pitch, self._imu_yaw,
            self._imu_ax, self._imu_ay, self._imu_az,
        )

    def _cb_imu_accel(self, timestamp, data, logconf) -> None:
        """Receive acceleration packet — updates cached accel values."""
        self._imu_ax = data.get("stateEstimate.ax", 0.0)
        self._imu_ay = data.get("stateEstimate.ay", 0.0)
        self._imu_az = data.get("stateEstimate.az", 0.0)

    # ── cflib connection status callbacks ─────────────────────────────────────

    def _cb_connected(self, uri: str) -> None:
        """Called by cflib when link is established — matches dead-reckoning-maneuvers.py."""
        self.error_occurred.emit(f"✓ Connected to {uri}")
        self.connected.emit()

    def _cb_disconnected(self, uri: str) -> None:
        """Called by cflib on clean disconnect."""
        self.error_occurred.emit(f"Disconnected from {uri}")
        self.disconnected.emit()

    def _cb_connection_failed(self, uri: str, msg: str) -> None:
        """Called by cflib when connection attempt fails."""
        self.error_occurred.emit(f"Connection failed: {msg}")
        self.disconnected.emit()

    def _cb_connection_lost(self, uri: str, msg: str) -> None:
        """Called by cflib when existing connection drops."""
        self.error_occurred.emit(f"Connection lost: {msg}")
        self.disconnected.emit()
