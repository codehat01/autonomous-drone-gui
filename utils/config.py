# ── Drone Connection ──────────────────────────────────────────────────────────
# udpdriver.py hardcodes 192.168.43.42:2390 (drone hotspot IP) — URI just needs udp:// prefix
DRONE_URI = "udp://192.168.43.42:2390"
DRONE_IP  = "192.168.43.42"
TELEMETRY_PERIOD_MS = 10   # SENSOR_PERIOD_MS = 10 from all scripts

# ── Flight Parameters (from dead-reckoning-maneuvers.py) ──────────────────────
TARGET_HEIGHT      = 0.3   # 0.3m from dead-reckoning-maneuvers.py
TAKEOFF_TIME       = 1.0   # seconds
HOVER_DURATION     = 20.0  # seconds
LANDING_TIME       = 0.5   # seconds
MAX_SPEED          = 0.4   # m/s max speed (from simple capping logic)
MAX_HEIGHT         = 1.5   # m hard ceiling

# ── PID Controller (from dead-reckoning-maneuvers.py) ─────────────────────────
POSITION_KP              = 1.0
POSITION_KI              = 0.03
POSITION_KD              = 0.0
VELOCITY_KP              = 0.7
VELOCITY_KI              = 0.01
VELOCITY_KD              = 0.0
MAX_CORRECTION           = 0.7
VELOCITY_SMOOTHING_ALPHA = 0.85   # from dead-reckoning-maneuvers.py
VELOCITY_THRESHOLD       = 0.005  # m/s — from all scripts
DRIFT_COMPENSATION_RATE  = 0.004  # from dead-reckoning-maneuvers.py
PERIODIC_RESET_INTERVAL  = 90.0   # seconds
MAX_POSITION_ERROR       = 2.0    # metres

# ── Sensor / Optical Flow ─────────────────────────────────────────────────────
# SENSOR_PERIOD_MS = 10 → DT = 0.01
DT                  = TELEMETRY_PERIOD_MS / 1000.0   # 0.01 s
CONTROL_UPDATE_RATE = 0.02   # 50 Hz control loop (from all scripts)

# Velocity constant formula from test_optical_flow_sensor.py:
#   velocity_constant = (5.4 * DEG_TO_RAD) / (30.0 * DT)
# 5.4° sensor FoV, 30 pixel resolution, DT = sample time
import math as _math
OPTICAL_FLOW_FOV_DEG    = 5.4     # test_optical_flow_sensor.py (more accurate)
OPTICAL_FLOW_RESOLUTION = 30
DEG_TO_RAD              = _math.pi / 180.0
VELOCITY_CONSTANT       = (OPTICAL_FLOW_FOV_DEG * DEG_TO_RAD) / (OPTICAL_FLOW_RESOLUTION * DT)
OPTICAL_FLOW_SCALE      = 4.4    # empirical fallback (dead-reckoning-maneuvers.py)
EMA_ALPHA               = 0.2    # read_motion_flow_data.py EMA filter
IIR_ALPHA               = 0.7    # test_optical_flow_sensor.py IIR alpha

# ── Sensor Safety ─────────────────────────────────────────────────────────────
LOW_BATTERY_THRESHOLD        = 2.9    # volts — from all scripts
HEIGHT_SENSOR_MIN_CHANGE     = 0.005  # metres — dead-reckoning-maneuvers.py
DATA_TIMEOUT_THRESHOLD       = 0.2   # seconds — dead-reckoning-maneuvers.py

# ── Maneuver Parameters (from dead-reckoning-maneuvers.py) ────────────────────
MANEUVER_DISTANCE            = 0.5   # metres
MANEUVER_THRESHOLD           = 0.10  # within 10cm = "arrived"
WAYPOINT_TIMEOUT             = 60.0  # seconds
WAYPOINT_STABILIZATION_TIME  = 0.5   # seconds at each waypoint
JOYSTICK_SENSITIVITY         = 0.2

# Momentum compensation (from dead-reckoning-maneuvers.py)
MOMENTUM_COMPENSATION_TIME   = 0.10
SETTLING_DURATION            = 0.1
SETTLING_CORRECTION_FACTOR   = 0.5

# ── Firmware Parameters (from dead-reckoning-maneuvers.py apply_firmware_parameters) ──
ENABLE_FIRMWARE_PARAMS       = False
FW_THRUST_BASE               = 24000   # posCtlPid.thrustBase
FW_Z_POS_KP                  = 1.6    # posCtlPid.zKp
FW_Z_VEL_KP                  = 15.0   # velCtlPid.vzKp

# ── NeoPixel (from dead-reckoning-maneuvers.py) ────────────────────────────────
CRTP_PORT_NEOPIXEL           = 0x09
NEOPIXEL_CHANNEL_SET_PIXEL   = 0x00
NEOPIXEL_CHANNEL_SHOW        = 0x01
NEOPIXEL_CHANNEL_CLEAR       = 0x02
NEOPIXEL_CHANNEL_BLINK       = 0x03
NP_SEND_RETRIES              = 3
NP_PACKET_DELAY              = 0.02
NP_LINK_SETUP_DELAY          = 0.12

# ── Trim corrections (from dead-reckoning-position-hold.py) ─────────────────────
# Applied as: total_vx = TRIM_VX + motion_vy,  total_vy = TRIM_VY + motion_vx
TRIM_VX = 0.1    # Forward/backward drift correction
TRIM_VY = -0.02  # Left/right drift correction

# ── Joystick (from height-hold-joystick.py / dead-reckoning-joystick-control.py) ──
JOYSTICK_VENDOR_ID   = 0x0079   # DragonRise Generic USB Joystick
JOYSTICK_PRODUCT_ID  = 0x0006
JOYSTICK_MAX_VEL     = 0.5      # m/s scaling (joystick ±1 → ±0.5 m/s)

# ── CSV Logging (from dead-reckoning-maneuvers.py) ────────────────────────────
DRONE_CSV_LOGGING            = False  # off by default

# ── Camera ────────────────────────────────────────────────────────────────────
WEBCAM_INDEX  = 0
PI_RTSP_URL   = "rtsp://192.168.43.1:8554/stream"
CAMERA_FPS    = 20           # reduced from 30 — less memory pressure
FRAME_WIDTH   = 320          # reduced from 640 — 921600→230400 bytes/frame
FRAME_HEIGHT  = 240          # reduced from 480 — YOLO still works well at 320×240

# ── YOLO ──────────────────────────────────────────────────────────────────────
YOLO_MODEL_PATH      = "models/yolov8n.pt"
YOLO_CONF_THRESHOLD  = 0.5
FOCAL_LENGTH_PX      = 500.0
AVG_PERSON_HEIGHT_M  = 1.7

# ── Security ──────────────────────────────────────────────────────────────────
REPLAY_WINDOW_SECONDS  = 5
REPLAY_NONCE_POOL_SIZE = 50
COMMAND_RATE_HZ        = 10

# ── System Monitor ────────────────────────────────────────────────────────────
MONITOR_INTERVAL_MS = 1000

# ── Indoor Map ────────────────────────────────────────────────────────────────
ROOM_SIZE_METERS = 5.0
MAP_TRAIL_LENGTH = 500

# ── Battery thresholds ────────────────────────────────────────────────────────
BATTERY_MIN_V   = 3.0
BATTERY_MAX_V   = 4.2
BATTERY_WARN_V  = 3.5   # amber warning below this
BATTERY_CRIT_V  = 3.2   # red critical below this
