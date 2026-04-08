import numpy as np
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                              QLabel, QPushButton, QFrame)
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QImage, QPixmap, QColor
from utils.theme import COLORS, card_style
from ui.widgets.led_indicator import LedIndicator
from ui.widgets.status_badge import StatusBadge


class CameraPanel(QWidget):
    """
    Ground Camera Feed panel.
    Displays live video frames from CameraService via set_frame().
    Source toggle between webcam and Pi RTSP stream.
    """

    PLACEHOLDER_W = 640
    PLACEHOLDER_H = 480

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_source = "webcam"
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        card = QFrame()
        card.setStyleSheet(card_style())
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # ── Header row ────────────────────────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel("GROUND CAMERA FEED")
        title.setObjectName("panel_title")
        self._live_led = LedIndicator(color=COLORS['accent_teal'], size=12)
        self._live_led.set_state(True)
        live_label = QLabel("LIVE")
        live_label.setObjectName("value_small")
        self._fps_label = QLabel("FPS: --")
        self._fps_label.setObjectName("fps_badge")   # styled via stylesheet
        header.addWidget(title)
        header.addWidget(self._live_led)
        header.addWidget(live_label)
        header.addStretch()
        header.addWidget(self._fps_label)
        layout.addLayout(header)

        # ── Sub-label ─────────────────────────────────────────────────────────
        sublabel = QLabel("Edge AI Vision System  |  Raspberry Pi Ground Station")
        sublabel.setObjectName("value_small")
        layout.addWidget(sublabel)

        # ── Video display ─────────────────────────────────────────────────────
        self._video_label = QLabel()
        self._video_label.setMinimumSize(self.PLACEHOLDER_W // 2, self.PLACEHOLDER_H // 2)
        self._video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._video_label.setObjectName("video_frame")
        self._show_placeholder()
        layout.addWidget(self._video_label, stretch=1)

        # ── Detection overlay badge ───────────────────────────────────────────
        self._detection_badge = QLabel("● NO TARGET")
        self._detection_badge.setObjectName("value_small")
        layout.addWidget(self._detection_badge, alignment=Qt.AlignmentFlag.AlignCenter)

        # ── Source toggle buttons — equal width, full row ─────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self._btn_webcam = QPushButton("WEBCAM")
        self._btn_webcam.setObjectName("btn_active")
        self._btn_webcam.setFixedHeight(30)
        self._btn_webcam.clicked.connect(lambda: self._select_source("webcam"))

        self._btn_rtsp = QPushButton("PI STREAM (RTSP)")
        self._btn_rtsp.setFixedHeight(30)
        self._btn_rtsp.clicked.connect(lambda: self._select_source("rtsp"))

        btn_row.addWidget(self._btn_webcam)
        btn_row.addWidget(self._btn_rtsp)
        layout.addLayout(btn_row)

        root.addWidget(card)

    def _show_placeholder(self) -> None:
        placeholder = QPixmap(self.PLACEHOLDER_W // 2, self.PLACEHOLDER_H // 2)
        placeholder.fill(QColor(COLORS['bg_primary']))
        self._video_label.setPixmap(placeholder)
        self._video_label.setText("Waiting for camera feed...")

    def _select_source(self, source: str) -> None:
        self._current_source = source
        if source == "webcam":
            self._btn_webcam.setObjectName("btn_active")
            self._btn_rtsp.setObjectName("")
        else:
            self._btn_rtsp.setObjectName("btn_active")
            self._btn_webcam.setObjectName("")
        for btn in [self._btn_webcam, self._btn_rtsp]:
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    @pyqtSlot(object)   # np.ndarray
    def set_frame(self, frame: np.ndarray) -> None:
        if frame is None or frame.size == 0:
            return
        h, w, ch = frame.shape
        bytes_per_line = ch * w
        qt_img = QImage(frame.data, w, h, bytes_per_line,
                        QImage.Format.Format_BGR888)
        pixmap = QPixmap.fromImage(qt_img).scaled(
            self._video_label.width(),
            self._video_label.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation)
        self._video_label.setPixmap(pixmap)
        self._video_label.setText("")

    @pyqtSlot(float)
    def set_fps(self, fps: float) -> None:
        self._fps_label.setText(f"FPS: {fps:.1f}")

    @pyqtSlot(bool, float)
    def set_detection(self, detected: bool, confidence: float) -> None:
        if detected:
            self._detection_badge.setText(f"● PERSON DETECTED  ({confidence * 100:.0f}%)")
            self._detection_badge.setStyleSheet(
                "color: " + COLORS['accent_green'] + "; font-weight: bold; letter-spacing: 1px;")
        else:
            self._detection_badge.setText("● NO TARGET")
            self._detection_badge.setStyleSheet(
                "color: " + COLORS['text_secondary'] + "; font-weight: bold; letter-spacing: 1px;")
