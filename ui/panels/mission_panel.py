import time
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                              QLabel, QPushButton, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QTimer
from utils.theme import COLORS, card_style
from ui.widgets.status_badge import StatusBadge


class MissionPanel(QWidget):
    """
    Mission status and quick-action buttons.
    Shows current mode, target lock status, command counters, uptime.
    Emits signals for TAKEOFF, HOVER, LAND quick actions.
    """

    takeoff_requested = pyqtSignal()
    hover_requested   = pyqtSignal()
    land_requested    = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._session_start = time.time()
        self._cmd_sent = 0
        self._cmd_blocked = 0
        self._setup_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick_uptime)
        self._timer.start(1000)

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setStyleSheet(card_style())
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("MISSION STATUS")
        title.setObjectName("panel_title")
        layout.addWidget(title)

        # ── Status grid — equal column stretch so labels/badges align ─────────
        grid = QGridLayout()
        grid.setSpacing(6)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 2)
        self._mode_badge   = StatusBadge("MANUAL",    active=False)
        self._target_badge = StatusBadge("NO TARGET", active=False)
        mode_lbl   = QLabel("Mode:");   mode_lbl.setObjectName("value_small")
        target_lbl = QLabel("Target:"); target_lbl.setObjectName("value_small")
        grid.addWidget(mode_lbl,           0, 0)
        grid.addWidget(self._mode_badge,   0, 1)
        grid.addWidget(target_lbl,         1, 0)
        grid.addWidget(self._target_badge, 1, 1)
        layout.addLayout(grid)

        self._counter_lbl = QLabel("Cmds: 0 sent  |  0 blocked")
        self._counter_lbl.setObjectName("value_small")
        layout.addWidget(self._counter_lbl)

        self._uptime_lbl = QLabel("Uptime: 00:00:00")
        self._uptime_lbl.setObjectName("value_small")
        # Use objectName for uptime color so it inherits from theme stylesheet
        self._uptime_lbl.setObjectName("uptime_label")
        layout.addWidget(self._uptime_lbl)

        action_lbl = QLabel("QUICK ACTIONS")
        action_lbl.setObjectName("value_small")
        layout.addWidget(action_lbl)

        # ── Quick-action buttons — objectNames for theme-safe styling ─────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self._btn_takeoff = QPushButton("TAKEOFF")
        self._btn_hover   = QPushButton("HOVER")
        self._btn_land    = QPushButton("LAND")
        for btn in [self._btn_takeoff, self._btn_hover, self._btn_land]:
            btn.setFixedHeight(32)
        self._btn_takeoff.setObjectName("btn_takeoff")
        self._btn_hover.setObjectName("btn_hover")
        self._btn_land.setObjectName("btn_land")
        self._btn_takeoff.clicked.connect(self.takeoff_requested.emit)
        self._btn_hover.clicked.connect(self.hover_requested.emit)
        self._btn_land.clicked.connect(self.land_requested.emit)
        btn_row.addWidget(self._btn_takeoff)
        btn_row.addWidget(self._btn_hover)
        btn_row.addWidget(self._btn_land)
        layout.addLayout(btn_row)

        root.addWidget(card)

    def _tick_uptime(self) -> None:
        elapsed = int(time.time() - self._session_start)
        h, rem = divmod(elapsed, 3600)
        m, s = divmod(rem, 60)
        self._uptime_lbl.setText(f"Uptime: {h:02d}:{m:02d}:{s:02d}")

    @pyqtSlot(str)
    def set_mode(self, mode: str) -> None:
        self._mode_badge.set_label(mode)
        self._mode_badge.set_active(mode == "AUTO TRACK")

    @pyqtSlot(bool)
    def set_target_locked(self, locked: bool) -> None:
        self._target_badge.set_label("LOCKED" if locked else "NO TARGET")
        self._target_badge.set_active(locked)

    @pyqtSlot(int, int)
    def set_command_counts(self, sent: int, blocked: int) -> None:
        self._cmd_sent = sent
        self._cmd_blocked = blocked
        self._counter_lbl.setText(f"Cmds: {sent} sent  |  {blocked} blocked")
