"""
YoloService — QThread that receives BGR frames and runs YOLOv8 inference.

Only detects persons (class_id = 0).  Picks the highest-confidence
detection per frame.  Estimates distance from bounding-box height using
the thin-lens formula:
    distance = (FOCAL_LENGTH_PX * AVG_PERSON_HEIGHT_M) / bbox_height_px

Emits:
    tracking_ready(TrackingData) — filled with detection result + velocity cmds
    annotated_frame(np.ndarray)  — BGR frame with bounding box drawn
"""
import time
import queue
from typing import Optional

import cv2
import numpy as np

from PyQt6.QtCore import QThread, pyqtSignal

from models.tracking_data import TrackingData
from controllers.tracking_controller import TrackingController
from utils.config import (
    YOLO_MODEL_PATH, YOLO_CONF_THRESHOLD,
    FOCAL_LENGTH_PX, AVG_PERSON_HEIGHT_M,
    FRAME_WIDTH, FRAME_HEIGHT,
)

_PERSON_CLASS_ID = 0


class YoloService(QThread):
    """
    Inference thread.  Frames are queued via push_frame(); processed FIFO.
    Drops frames when inference is slower than capture (queue depth = 1).
    """

    tracking_ready  = pyqtSignal(object)   # TrackingData
    annotated_frame = pyqtSignal(object)   # np.ndarray BGR

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._queue: queue.Queue = queue.Queue(maxsize=1)
        self._tracker = TrackingController(frame_w=FRAME_WIDTH, frame_h=FRAME_HEIGHT)
        self._model = None
        self._model_path = YOLO_MODEL_PATH

    # ── Public API ────────────────────────────────────────────────────────────

    def push_frame(self, frame: np.ndarray) -> None:
        """Non-blocking frame push. Drops if queue is full (keeps latest)."""
        try:
            self._queue.put_nowait(frame)
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(frame)
            except queue.Full:
                pass

    def stop(self) -> None:
        self._running = False
        self._queue.put(None)  # unblock get()
        self.wait()

    # ── Thread entry point ────────────────────────────────────────────────────

    def run(self) -> None:
        self._running = True
        self._model = self._load_model()

        while self._running:
            frame = self._queue.get()
            if frame is None or not self._running:
                break
            self._process_frame(frame)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _load_model(self):
        try:
            from ultralytics import YOLO
            model = YOLO(self._model_path)
            model.fuse()   # minor inference speed boost
            return model
        except Exception as e:
            print(f"[YoloService] Failed to load model: {e}")
            return None

    def _process_frame(self, frame: np.ndarray) -> None:
        t0 = time.monotonic()

        if self._model is None:
            td = TrackingData(
                person_detected=False,
                bbox=(0, 0, 0, 0),
                center_x=FRAME_WIDTH // 2,
                center_y=FRAME_HEIGHT // 2,
                confidence=0.0,
                distance_estimate=0.0,
                frame_fps=0.0,
                cmd_vx=0.0,
                cmd_vy=0.0,
            )
            self.tracking_ready.emit(td)
            self.annotated_frame.emit(frame.copy())
            return

        # Inference runs at FRAME_WIDTH×FRAME_HEIGHT (320×240) — low memory pressure
        try:
            results = self._model.predict(
                frame,
                classes=[_PERSON_CLASS_ID],
                conf=YOLO_CONF_THRESHOLD,
                verbose=False,
                imgsz=320,
            )
        except Exception as e:
            print(f"[YoloService] Inference error: {e}")
            return

        fps = 1.0 / max(time.monotonic() - t0, 1e-6)
        best = self._best_detection(results)
        annotated = frame.copy()

        if best is not None:
            x1, y1, x2, y2, conf = best
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2
            bbox_h = max(y2 - y1, 1)
            dist = (FOCAL_LENGTH_PX * AVG_PERSON_HEIGHT_M) / bbox_h

            td = TrackingData(
                person_detected=True,
                bbox=(x1, y1, x2, y2),
                center_x=cx,
                center_y=cy,
                confidence=conf,
                distance_estimate=round(dist, 2),
                frame_fps=round(fps, 1),
                cmd_vx=0.0,
                cmd_vy=0.0,
            )
            # Fill in velocity commands from tracking controller
            vx, vy = self._tracker.compute(td)
            td = TrackingData(
                person_detected=td.person_detected,
                bbox=td.bbox,
                center_x=td.center_x,
                center_y=td.center_y,
                confidence=td.confidence,
                distance_estimate=td.distance_estimate,
                frame_fps=td.frame_fps,
                cmd_vx=vx,
                cmd_vy=vy,
            )

            # Draw bounding box + label
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 212, 170), 2)
            label = f"Person {conf:.0%}  {dist:.1f}m"
            cv2.putText(annotated, label, (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 212, 170), 2)
            cv2.circle(annotated, (cx, cy), 4, (255, 80, 80), -1)
        else:
            td = TrackingData(
                person_detected=False,
                bbox=(0, 0, 0, 0),
                center_x=FRAME_WIDTH // 2,
                center_y=FRAME_HEIGHT // 2,
                confidence=0.0,
                distance_estimate=0.0,
                frame_fps=round(fps, 1),
                cmd_vx=0.0,
                cmd_vy=0.0,
            )

        self.tracking_ready.emit(td)
        self.annotated_frame.emit(annotated)

    @staticmethod
    def _best_detection(results) -> Optional[tuple]:
        """Return (x1, y1, x2, y2, conf) of highest-confidence person, or None."""
        best_conf = -1.0
        best = None
        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                cls = int(box.cls[0])
                if cls != _PERSON_CLASS_ID:
                    continue
                conf = float(box.conf[0])
                if conf > best_conf:
                    best_conf = conf
                    x1, y1, x2, y2 = (int(v) for v in box.xyxy[0])
                    best = (x1, y1, x2, y2, conf)
        return best
