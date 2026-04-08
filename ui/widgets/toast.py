"""
ToastNotification — floating overlay popup for system alerts.

Usage:
    toast = ToastNotification(parent_window, title="Drone Disconnected",
                              message="Connection lost.", level="error")
    toast.show_toast()

Auto-dismisses after 4 seconds with a fade-out animation.
Levels: "error" (red), "warning" (amber), "info" (teal), "success" (green)
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QPainter, QColor, QPainterPath

from utils.theme import COLORS, FONT_MONO, FONT_UI

_LEVEL_COLORS = {
    "error":   ("#ef4444", "#450a0a"),
    "warning": ("#f59e0b", "#451a03"),
    "info":    ("#00d4aa", "#022c22"),
    "success": ("#10b981", "#022c22"),
}

_LEVEL_ICONS = {
    "error":   "✖",
    "warning": "⚠",
    "info":    "ℹ",
    "success": "✔",
}


class ToastNotification(QWidget):
    """Floating, auto-dismissing toast notification widget."""

    def __init__(self, parent: QWidget, title: str, message: str,
                 level: str = "info", duration_ms: int = 4000):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._opacity = 1.0
        self._duration_ms = duration_ms
        self._level = level
        self._build_ui(title, message, level)

    def _build_ui(self, title: str, message: str, level: str) -> None:
        accent, bg = _LEVEL_COLORS.get(level, _LEVEL_COLORS["info"])
        icon = _LEVEL_ICONS.get(level, "ℹ")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        card = QWidget()
        card.setObjectName("toast_card")
        card.setStyleSheet(f"""
            QWidget#toast_card {{
                background: {bg};
                border: 2px solid {accent};
                border-radius: 12px;
            }}
        """)
        card.setMinimumWidth(340)
        card.setMaximumWidth(420)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(6)

        # Header row
        header = QHBoxLayout()
        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet(
            f"color: {accent}; font-size: 18px; font-weight: bold;")
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"color: {accent}; font-size: 13px; font-weight: bold; "
            f"font-family: {FONT_MONO};")
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(22, 22)
        close_btn.setStyleSheet(
            f"background: transparent; color: {accent}; "
            "border: none; font-size: 12px; font-weight: bold;")
        close_btn.clicked.connect(self.close)

        header.addWidget(icon_lbl)
        header.addWidget(title_lbl)
        header.addStretch()
        header.addWidget(close_btn)
        card_layout.addLayout(header)

        # Message
        msg_lbl = QLabel(message)
        msg_lbl.setWordWrap(True)
        msg_lbl.setStyleSheet(
            f"color: #e2e8f0; font-size: 12px; font-family: {FONT_UI};")
        card_layout.addWidget(msg_lbl)

        layout.addWidget(card)

    def show_toast(self) -> None:
        """Position in bottom-right corner of parent and auto-dismiss."""
        parent = self.parent()
        if parent is not None:
            self.adjustSize()
            pw, ph = parent.width(), parent.height()
            w, h = self.sizeHint().width(), self.sizeHint().height()
            self.setGeometry(pw - w - 20, ph - h - 60, w, h)
        self.show()
        self.raise_()

        # Auto-dismiss timer
        QTimer.singleShot(self._duration_ms, self._start_fade_out)

    def _start_fade_out(self) -> None:
        self._anim = QPropertyAnimation(self, b"windowOpacity")
        self._anim.setDuration(600)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._anim.finished.connect(self.close)
        self._anim.start()
