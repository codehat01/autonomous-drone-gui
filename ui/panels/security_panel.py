import time
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                              QLabel, QListWidget, QListWidgetItem, QFrame)
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QColor
from utils.theme import COLORS, card_style, FONT_MONO
from ui.widgets.status_badge import StatusBadge
from ui.widgets.led_indicator import LedIndicator
from models.security_event import SecurityEvent

MAX_LOG_ENTRIES = 200


class SecurityPanel(QWidget):
    """
    Security monitoring panel.
    Shows token auth status, replay guard, range check badges.
    Streams all SecurityEvents into a terminal-style log.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._total_sent = 0
        self._total_blocked = 0
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setStyleSheet(card_style())
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("SECURITY MONITOR")
        title.setObjectName("panel_title")
        layout.addWidget(title)

        # ── Status badges row ──────────────────────────────────────────────────
        badges_row = QHBoxLayout()
        self._token_badge   = StatusBadge("Token Auth",   active=True)
        self._replay_badge  = StatusBadge("Replay Guard", active=True)
        self._range_badge   = StatusBadge("Range Check",  active=True)
        for badge in [self._token_badge, self._replay_badge, self._range_badge]:
            badge.set_active(True)
            badges_row.addWidget(badge)
        layout.addLayout(badges_row)

        # ── Stats row ──────────────────────────────────────────────────────────
        stats_row = QHBoxLayout()
        self._stats_lbl = QLabel("Sent: 0  |  Blocked: 0  |  Auth Rate: 100%")
        self._stats_lbl.setObjectName("value_small")
        stats_row.addWidget(self._stats_lbl)
        layout.addLayout(stats_row)

        # ── Last event highlight ───────────────────────────────────────────────
        self._last_event_lbl = QLabel("Last Event: —")
        self._last_event_lbl.setObjectName("value_small")
        self._last_event_lbl.setStyleSheet(
            f"color: {COLORS['accent_teal']}; font-family: {FONT_MONO};")
        layout.addWidget(self._last_event_lbl)

        # ── Terminal log ───────────────────────────────────────────────────────
        log_lbl = QLabel("COMMAND LOG")
        log_lbl.setObjectName("value_small")
        layout.addWidget(log_lbl)

        self._log = QListWidget()
        self._log.setObjectName("security_log")
        self._log.setMinimumHeight(120)
        layout.addWidget(self._log, stretch=1)

        root.addWidget(card)

    @pyqtSlot(object)   # SecurityEvent
    def add_event(self, event: SecurityEvent) -> None:
        ts = time.strftime("%H:%M:%S", time.localtime(event.timestamp))
        text = f"[{ts}] {event.event_type:<20} {event.verdict:<10} {event.details}"

        item = QListWidgetItem(text)
        item.setFont(self._log.font())

        if event.verdict == "ALLOWED":
            item.setForeground(QColor(COLORS['accent_green']))
            self._total_sent += 1
        elif event.event_type == "REPLAY_ATTACK":
            item.setForeground(QColor(COLORS['accent_red']))
            self._total_blocked += 1
            self._replay_badge.set_active(False)
        elif event.event_type == "INVALID_RANGE":
            item.setForeground(QColor(COLORS['accent_amber']))
            self._total_blocked += 1
            self._range_badge.set_active(False)
        else:
            item.setForeground(QColor(COLORS['text_secondary']))

        self._log.insertItem(0, item)
        if self._log.count() > MAX_LOG_ENTRIES:
            self._log.takeItem(self._log.count() - 1)

        # Update stats
        total = self._total_sent + self._total_blocked
        rate = (self._total_sent / total * 100) if total > 0 else 100.0
        self._stats_lbl.setText(
            f"Sent: {self._total_sent}  |  Blocked: {self._total_blocked}  |  Auth Rate: {rate:.1f}%")
        self._last_event_lbl.setText(f"Last Event: [{ts}] {event.event_type} → {event.verdict}")

    def reset_alerts(self) -> None:
        """Reset all badge states to active/green."""
        for badge in [self._token_badge, self._replay_badge, self._range_badge]:
            badge.set_active(True)
