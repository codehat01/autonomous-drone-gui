"""
CommandValidator — range-check drone velocity commands.

Ensures vx, vy stay within configured speed limits and height
stays within [MIN_HEIGHT, MAX_HEIGHT].
"""
from utils.config import MAX_SPEED, TARGET_HEIGHT, MAX_HEIGHT


MIN_HEIGHT = 0.05   # 5 cm — below this is effectively on the ground


class CommandValidator:
    """
    Validates that a command (vx, vy, height) is within safe operating limits.

    Returns (is_valid: bool, reason: str).
    """

    def __init__(
        self,
        max_speed: float = MAX_SPEED,
        max_height: float = MAX_HEIGHT,
        min_height: float = MIN_HEIGHT,
    ):
        self._max_speed = max_speed
        self._max_height = max_height
        self._min_height = min_height

    def validate(
        self,
        vx: float,
        vy: float,
        height: float,
    ) -> tuple[bool, str]:
        if abs(vx) > self._max_speed:
            return False, f"vx={vx:.3f} exceeds MAX_SPEED={self._max_speed}"
        if abs(vy) > self._max_speed:
            return False, f"vy={vy:.3f} exceeds MAX_SPEED={self._max_speed}"
        if height > self._max_height:
            return False, f"height={height:.2f} exceeds MAX_HEIGHT={self._max_height}"
        if height < self._min_height:
            return False, f"height={height:.2f} below MIN_HEIGHT={self._min_height}"
        return True, "OK"
