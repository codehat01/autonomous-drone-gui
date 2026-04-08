"""
SecurityPage — Full-screen security monitoring + command audit.

Shows:
  - SecurityPanel (full width)
  - Command statistics (sent / blocked / auth rate)
  - Live event feed with REPLAY_ATTACK / INVALID_TOKEN / INVALID_RANGE / VALID
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                              QLabel, QFrame, QScrollArea)
from PyQt6.QtCore import pyqtSlot, Qt

from utils.theme import COLORS, card_style, FONT_MONO
from ui.panels.security_panel import SecurityPanel


class SecurityPage(QWidget):
    """Full-page security audit view — scrollable."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        container.setMinimumSize(900, 600)
        inner = QVBoxLayout(container)
        inner.setContentsMargins(16, 12, 16, 12)
        inner.setSpacing(10)

        # Title
        title = QLabel("SECURITY MONITOR  —  HMAC-SHA256  ·  REPLAY DETECTION  ·  RANGE VALIDATION")
        title.setStyleSheet(
            f"color: {COLORS['accent_red']}; font-size: 15px; font-weight: bold; "
            f"font-family: {FONT_MONO}; letter-spacing: 2px;")
        inner.addWidget(title)

        # Stats bar
        inner.addWidget(self._build_stats_bar())

        # Full security panel
        self.security_panel = SecurityPanel()
        inner.addWidget(self.security_panel, stretch=1)

        scroll.setWidget(container)
        root.addWidget(scroll)

    def _build_stats_bar(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(card_style())
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(30)

        for label, color, attr in [
            ("Commands Sent",    COLORS['accent_green'],  "_stat_sent"),
            ("Commands Blocked", COLORS['accent_red'],    "_stat_blocked"),
            ("Auth Rate",        COLORS['accent_teal'],   "_stat_rate"),
            ("Replay Attacks",   COLORS['accent_amber'],  "_stat_replay"),
            ("Invalid Range",    COLORS['accent_purple'], "_stat_range"),
        ]:
            frame = QFrame()
            frame.setStyleSheet(
                f"background: {COLORS['bg_primary']}; border-radius: 8px; padding: 6px;")
            inner = QVBoxLayout(frame)
            inner.setContentsMargins(8, 6, 8, 6)
            lbl = QLabel(label)
            lbl.setObjectName("value_small")
            val = QLabel("0")
            val.setStyleSheet(
                f"color: {color}; font-size: 26px; font-weight: bold; "
                f"font-family: {FONT_MONO};")
            inner.addWidget(lbl)
            inner.addWidget(val)
            setattr(self, attr, val)
            layout.addWidget(frame)

        layout.addStretch()
        return card

    @pyqtSlot(int, int)
    def set_counts(self, sent: int, blocked: int) -> None:
        self._stat_sent.setText(str(sent))
        self._stat_blocked.setText(str(blocked))
        rate = (sent / (sent + blocked) * 100) if (sent + blocked) > 0 else 100.0
        self._stat_rate.setText(f"{rate:.0f}%")

    @pyqtSlot(int)
    def set_replay_count(self, n: int) -> None:
        self._stat_replay.setText(str(n))

    @pyqtSlot(int)
    def set_range_count(self, n: int) -> None:
        self._stat_range.setText(str(n))
