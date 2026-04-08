"""
ColourTracker — HSV-based object tracker.

Directly derived from opecv-object-detection.py:
  - HSV colour range masking (default: orange)
  - Erosion + dilation noise reduction
  - Contour detection, largest contour selection
  - 10-point deque smoothing (matches smooth_x/y deque maxlen=10)
  - "Object Lost!" fallback to last known position

Can be used standalone (run on a frame) or injected into YoloService
as a fallback/alternative tracker.

Usage:
    ct = ColourTracker()
    result = ct.process(frame)   # returns ColourTrackResult
"""
from collections import deque
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np


@dataclass
class ColourTrackResult:
    detected: bool
    center_x: int
    center_y: int
    bbox: tuple             # (x, y, w, h)
    smoothed_x: int
    smoothed_y: int
    lost: bool              # True if using last known position


# Default: orange — matches opecv-object-detection.py
_DEFAULT_LOWER = np.array([5, 100, 100])
_DEFAULT_UPPER = np.array([15, 255, 255])

# Structural elements for morphological ops — matches Python-Script
_KERNEL = np.ones((5, 5), np.uint8)
_MIN_AREA = 500             # Minimum contour area threshold (matches Python-Script)
_SMOOTH_WIN = 10            # Deque maxlen — matches smooth_x/y deque maxlen=10


class ColourTracker:
    """
    Tracks a coloured object in a BGR frame using HSV masking.
    Implements the same algorithm as opecv-object-detection.py.
    """

    def __init__(
        self,
        lower_hsv: Optional[np.ndarray] = None,
        upper_hsv: Optional[np.ndarray] = None,
    ):
        self._lower = lower_hsv if lower_hsv is not None else _DEFAULT_LOWER.copy()
        self._upper = upper_hsv if upper_hsv is not None else _DEFAULT_UPPER.copy()

        # Smoothing deques — matches smooth_x = deque(maxlen=10) in Python-Script
        self._smooth_x: deque[int] = deque(maxlen=_SMOOTH_WIN)
        self._smooth_y: deque[int] = deque(maxlen=_SMOOTH_WIN)
        self._last_x: Optional[int] = None
        self._last_y: Optional[int] = None

    def process(self, frame: np.ndarray) -> ColourTrackResult:
        """
        Detect coloured object in frame and return tracking result.
        Exact algorithm from opecv-object-detection.py.
        """
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self._lower, self._upper)

        # Noise reduction — matches Python-Script
        mask = cv2.erode(mask,  _KERNEL, iterations=1)
        mask = cv2.dilate(mask, _KERNEL, iterations=2)

        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if contours:
            largest = max(contours, key=cv2.contourArea)
            if cv2.contourArea(largest) > _MIN_AREA:
                x, y, w, h = cv2.boundingRect(largest)
                cx = x + w // 2
                cy = y + h // 2

                self._smooth_x.append(cx)
                self._smooth_y.append(cy)

                sx = int(sum(self._smooth_x) / len(self._smooth_x))
                sy = int(sum(self._smooth_y) / len(self._smooth_y))

                self._last_x, self._last_y = sx, sy

                return ColourTrackResult(
                    detected=True,
                    center_x=cx,
                    center_y=cy,
                    bbox=(x, y, w, h),
                    smoothed_x=sx,
                    smoothed_y=sy,
                    lost=False,
                )

        # Object not found — return last known position (matches Python-Script behaviour)
        if self._last_x is not None:
            return ColourTrackResult(
                detected=False,
                center_x=self._last_x,
                center_y=self._last_y,
                bbox=(0, 0, 0, 0),
                smoothed_x=self._last_x,
                smoothed_y=self._last_y,
                lost=True,
            )

        return ColourTrackResult(
            detected=False,
            center_x=0, center_y=0,
            bbox=(0, 0, 0, 0),
            smoothed_x=0, smoothed_y=0,
            lost=False,
        )

    def annotate(self, frame: np.ndarray, result: ColourTrackResult) -> np.ndarray:
        """
        Draw bounding box, trajectory line, and status text on frame.
        Matches the visual output of opecv-object-detection.py.
        """
        out = frame.copy()
        if result.detected:
            x, y, w, h = result.bbox
            # Green bounding box — matches Python-Script
            cv2.rectangle(out, (x, y), (x + w, y + h), (0, 255, 0), 2)
            # Red smoothed centre dot
            cv2.circle(out, (result.smoothed_x, result.smoothed_y), 5, (0, 0, 255), -1)
            # Trajectory line if we have > 1 point
            if len(self._smooth_x) > 1:
                prev_x = int(sum(list(self._smooth_x)[:-1]) / (len(self._smooth_x) - 1))
                prev_y = int(sum(list(self._smooth_y)[:-1]) / (len(self._smooth_y) - 1))
                cv2.line(out,
                         (prev_x, prev_y),
                         (result.smoothed_x, result.smoothed_y),
                         (255, 0, 0), 2)   # Blue trajectory line
            # Coordinates
            cv2.putText(out,
                        f"({result.smoothed_x}, {result.smoothed_y})",
                        (result.smoothed_x + 10, result.smoothed_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        elif result.lost:
            cv2.putText(out,
                        "Object Lost!",
                        (result.center_x, result.center_y - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        return out

    def set_colour_range(
        self,
        lower_hsv: np.ndarray,
        upper_hsv: np.ndarray,
    ) -> None:
        """Hot-swap colour range (e.g. switch from orange to red)."""
        self._lower = lower_hsv
        self._upper = upper_hsv

    def reset(self) -> None:
        self._smooth_x.clear()
        self._smooth_y.clear()
        self._last_x = None
        self._last_y = None
