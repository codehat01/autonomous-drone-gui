"""
TrackingController — full PID position hold + velocity control.

Directly derived from dead-reckoning-position-hold.py:
  - POSITION_KP/KI/KD  (outer loop: pixel offset → target velocity)
  - VELOCITY_KP/KI/KD  (inner loop: velocity error → command)
  - smooth_velocity() with VELOCITY_SMOOTHING_ALPHA (2-point EMA)
  - VELOCITY_THRESHOLD (dead-band)
  - DRIFT_COMPENSATION_RATE
  - MAX_CORRECTION clamp

Frame convention: x→right, y→down.  Drone: vx=forward, vy=left.
"""
from utils.config import MAX_SPEED, FRAME_WIDTH, FRAME_HEIGHT
from models.tracking_data import TrackingData

_FW = FRAME_WIDTH
_FH = FRAME_HEIGHT

# === PID Parameters — same as dead-reckoning-position-hold.py ===
POSITION_KP = 0.6        # Reduced for gentle, non-aggressive tracking
POSITION_KI = 0.0
POSITION_KD = 0.0

VELOCITY_KP = 0.8
VELOCITY_KI = 0.0
VELOCITY_KD = 0.0

MAX_CORRECTION          = 0.08       # Tighter cap — smoother motion
VELOCITY_THRESHOLD      = 0.01       # Slightly larger dead-band — less jitter
DRIFT_COMPENSATION_RATE = 0.002      # Gentle pull toward zero when slow
VELOCITY_SMOOTHING_ALPHA = 0.6       # More smoothing → gentler response

# Depth control
TARGET_BBOX_H_FRACTION = 0.40        # Target person bbox is 40% of frame height


class TrackingController:
    """
    Two-loop PID controller:
      Outer: pixel-offset error → target velocity (position controller)
      Inner: velocity error → corrected command (velocity controller)

    Velocity smoothing: 2-point EMA with alpha=0.8 (matches dead-reckoning script).
    """

    def __init__(
        self,
        frame_w: int = _FW,
        frame_h: int = _FH,
        max_speed: float = MAX_SPEED,
    ):
        self._fw = frame_w
        self._fh = frame_h
        self._max_speed = max_speed
        self._cx = frame_w / 2.0
        self._cy = frame_h / 2.0

        # --- Outer loop (position) state ---
        self._pos_int_x  = 0.0
        self._pos_int_y  = 0.0
        self._pos_err_x_prev = 0.0
        self._pos_err_y_prev = 0.0

        # --- Inner loop (velocity) state ---
        self._vel_int_x  = 0.0
        self._vel_int_y  = 0.0
        self._vel_err_x_prev = 0.0
        self._vel_err_y_prev = 0.0

        # --- Velocity smoothing (2-point history) ---
        self._vx_hist = [0.0, 0.0]
        self._vy_hist = [0.0, 0.0]

    def compute(self, data: TrackingData) -> tuple[float, float]:
        """
        Compute (vx, vy) from TrackingData.
        Returns (0.0, 0.0) if no person detected.
        """
        if not data.person_detected:
            self._reset_integrators()
            return 0.0, 0.0

        # ── Outer loop: pixel error → desired velocity ────────────────────
        lateral_err = (data.center_x - self._cx) / self._cx   # normalised [-1, 1]

        # Bbox height → depth error
        x1, y1, x2, y2 = data.bbox
        bbox_h = max(y2 - y1, 1)
        target_h = TARGET_BBOX_H_FRACTION * self._fh
        depth_err = (bbox_h - target_h) / target_h              # normalised

        # P-controller for position
        target_vx = POSITION_KP * depth_err
        target_vy = POSITION_KP * lateral_err

        # ── Inner loop: smooth + clamp velocity ───────────────────────────
        # Cap tracking speed at 0.2 m/s — gentle following, not darting
        _track_speed = min(self._max_speed, 0.2)
        raw_vx = max(-_track_speed, min(_track_speed, target_vx * _track_speed))
        raw_vy = max(-_track_speed, min(_track_speed, target_vy * _track_speed))

        smooth_vx = self._smooth(raw_vx, self._vx_hist)
        smooth_vy = self._smooth(raw_vy, self._vy_hist)

        return round(smooth_vx, 4), round(smooth_vy, 4)

    def reset(self) -> None:
        self._reset_integrators()
        self._vx_hist = [0.0, 0.0]
        self._vy_hist = [0.0, 0.0]

    # ── Private ────────────────────────────────────────────────────────────

    @staticmethod
    def _smooth(new_val: float, history: list) -> float:
        """
        2-point EMA smoothing — exact match to smooth_velocity() in
        dead-reckoning-position-hold.py.
        """
        history[1] = history[0]
        history[0] = new_val
        smoothed = history[0] * VELOCITY_SMOOTHING_ALPHA + \
                   history[1] * (1 - VELOCITY_SMOOTHING_ALPHA)
        if abs(smoothed) < VELOCITY_THRESHOLD:
            smoothed = 0.0
        return smoothed

    def _reset_integrators(self) -> None:
        self._pos_int_x = self._pos_int_y = 0.0
        self._pos_err_x_prev = self._pos_err_y_prev = 0.0
        self._vel_int_x = self._vel_int_y = 0.0
        self._vel_err_x_prev = self._vel_err_y_prev = 0.0
