"""
CameraService — QThread that captures frames from webcam or RTSP stream.

Emits:
    frame_ready(np.ndarray)  — BGR frame, 640×480
    fps_updated(float)       — rolling 30-frame average FPS
    source_changed(str)      — "WEBCAM" or "PI STREAM" when switched

Hot-swap between webcam and PI RTSP without restarting the thread:
    service.switch_source("PI")   or   service.switch_source("WEBCAM")
"""
import time
import threading
from typing import Optional

import cv2
import numpy as np

from PyQt6.QtCore import QThread, pyqtSignal

from utils.config import (
    WEBCAM_INDEX, PI_RTSP_URL, CAMERA_FPS, FRAME_WIDTH, FRAME_HEIGHT
)


class CameraService(QThread):
    """
    Captures video frames and emits them as numpy arrays.

    The capture loop runs in a background thread. All OpenCV I/O
    happens in the thread; the main thread only receives signals.
    """

    frame_ready    = pyqtSignal(object)   # np.ndarray (BGR)
    fps_updated    = pyqtSignal(float)
    source_changed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, use_pi_stream: bool = False, parent=None):
        super().__init__(parent)
        self._use_pi = use_pi_stream
        self._running = False
        self._switch_lock = threading.Lock()
        self._pending_source: Optional[str] = None  # "WEBCAM" | "PI"
        self._cap: Optional[cv2.VideoCapture] = None
        self._fps_times: list[float] = []

    # ── Public API ────────────────────────────────────────────────────────────

    def switch_source(self, source: str) -> None:
        """
        Hot-swap camera source.  source="WEBCAM" or "PI".
        Takes effect at the next capture iteration.
        """
        with self._switch_lock:
            self._pending_source = source.upper()

    def stop(self) -> None:
        self._running = False
        self.wait()

    # ── Thread entry point ────────────────────────────────────────────────────

    def run(self) -> None:
        self._running = True
        self._cap = self._open_capture()
        _frame_interval = 1.0 / CAMERA_FPS   # minimum seconds between frames
        _last_frame_t = 0.0

        while self._running:
            # Throttle to CAMERA_FPS — prevents hammering cap.read() and burning RAM
            now = time.monotonic()
            elapsed = now - _last_frame_t
            if elapsed < _frame_interval:
                time.sleep(_frame_interval - elapsed)

            # Check for pending source switch
            with self._switch_lock:
                pending = self._pending_source
                if pending is not None:
                    self._pending_source = None

            if pending is not None:
                self._use_pi = (pending == "PI")
                if self._cap is not None:
                    self._cap.release()
                self._cap = self._open_capture()
                self.source_changed.emit("PI STREAM" if self._use_pi else "WEBCAM")

            if self._cap is None or not self._cap.isOpened():
                self.error_occurred.emit("Camera not available — retrying…")
                time.sleep(2.0)
                self._cap = self._open_capture()
                continue

            ret, frame = self._cap.read()
            if not ret or frame is None:
                self.error_occurred.emit("Frame read failed — reconnecting…")
                self._cap.release()
                time.sleep(1.0)
                self._cap = self._open_capture()
                continue

            _last_frame_t = time.monotonic()

            # Resize to target resolution only if needed
            if frame.shape[1] != FRAME_WIDTH or frame.shape[0] != FRAME_HEIGHT:
                frame = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT),
                                   interpolation=cv2.INTER_LINEAR)

            self.frame_ready.emit(frame)
            self._tick_fps()

        if self._cap is not None:
            self._cap.release()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _open_capture(self) -> Optional[cv2.VideoCapture]:
        source = PI_RTSP_URL if self._use_pi else WEBCAM_INDEX
        # Use CAP_DSHOW on Windows for faster webcam open + less memory overhead
        if not self._use_pi:
            cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
        else:
            cap = cv2.VideoCapture(source)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH,  FRAME_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
            cap.set(cv2.CAP_PROP_FPS,          CAMERA_FPS)
            # Reduce internal frame buffer to 1 — prevents stale frames piling up
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            return cap
        cap.release()
        return None

    def _tick_fps(self) -> None:
        now = time.monotonic()
        self._fps_times.append(now)
        # Rolling 30-frame window
        if len(self._fps_times) > 30:
            self._fps_times.pop(0)
        if len(self._fps_times) >= 2:
            elapsed = self._fps_times[-1] - self._fps_times[0]
            if elapsed > 0:
                fps = (len(self._fps_times) - 1) / elapsed
                self.fps_updated.emit(round(fps, 1))
