from dataclasses import dataclass, field


@dataclass
class TrackingData:
    person_detected: bool = False
    bbox: tuple = (0, 0, 0, 0)        # (x, y, w, h) pixels
    center_x: int = 0
    center_y: int = 0
    confidence: float = 0.0
    distance_estimate: float = 0.0    # meters, derived from bbox height
    frame_fps: float = 0.0
    cmd_vx: float = 0.0               # generated velocity command
    cmd_vy: float = 0.0
