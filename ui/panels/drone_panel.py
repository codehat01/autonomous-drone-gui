from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                              QLabel, QPushButton, QSlider, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from utils.theme import COLORS, card_style
from ui.widgets.status_badge import StatusBadge
from ui.widgets.led_indicator import LedIndicator


class DroneControlPanel(QWidget):
    """
    Manual drone control panel.
    Emits signals for connection, commands, and emergency stop.
    D-pad sends velocity commands. Height slider sets target altitude.
    """

    # Signals emitted to MainController
    connect_requested = pyqtSignal()
    disconnect_requested = pyqtSignal()
    emergency_stop_requested = pyqtSignal()
    manual_command = pyqtSignal(float, float, float, float)  # vx, vy, yaw_rate, height
    mode_changed = pyqtSignal(str)   # "AUTO" or "MANUAL"
    arm_requested = pyqtSignal(bool) # True=arm, False=disarm

    def __init__(self, parent=None):
        super().__init__(parent)
        self._connected = False
        self._mode = "MANUAL"
        self._target_height = 0.3
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setStyleSheet(card_style())
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # ── Title ──────────────────────────────────────────────────────────────
        title = QLabel("DRONE CONTROL")
        title.setObjectName("panel_title")
        layout.addWidget(title)

        # ── Connection row ─────────────────────────────────────────────────────
        conn_row = QHBoxLayout()
        self._conn_badge = StatusBadge("DISCONNECTED", active=False)
        self._btn_connect = QPushButton("CONNECT")
        self._btn_connect.setObjectName("btn_connect")
        self._btn_connect.setFixedHeight(30)
        self._btn_connect.clicked.connect(self._on_connect_click)
        conn_row.addWidget(self._conn_badge)
        conn_row.addStretch()
        conn_row.addWidget(self._btn_connect)
        layout.addLayout(conn_row)

        # ── Mode toggle ────────────────────────────────────────────────────────
        mode_row = QHBoxLayout()
        mode_lbl = QLabel("Mode:")
        mode_lbl.setObjectName("value_small")
        self._btn_manual = QPushButton("MANUAL")
        self._btn_manual.setObjectName("btn_active")
        self._btn_manual.setFixedHeight(28)
        self._btn_manual.clicked.connect(lambda: self._set_mode("MANUAL"))
        self._btn_auto = QPushButton("AUTO TRACK")
        self._btn_auto.setFixedHeight(28)
        self._btn_auto.clicked.connect(lambda: self._set_mode("AUTO"))
        mode_row.addWidget(mode_lbl)
        mode_row.addWidget(self._btn_manual)
        mode_row.addWidget(self._btn_auto)
        layout.addLayout(mode_row)

        # ── D-pad ──────────────────────────────────────────────────────────────
        dpad_label = QLabel("MANUAL CONTROL")
        dpad_label.setObjectName("value_small")
        dpad_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(dpad_label)

        # Outer HBox centres the grid horizontally
        dpad_outer = QHBoxLayout()
        dpad_outer.setContentsMargins(0, 0, 0, 0)

        dpad = QGridLayout()
        dpad.setSpacing(6)
        # Equal stretch on all 3 columns so the grid stays centred
        for col in range(3):
            dpad.setColumnStretch(col, 1)
        for row in range(3):
            dpad.setRowStretch(row, 1)

        self._btn_forward = self._dpad_button("▲")
        self._btn_back    = self._dpad_button("▼")
        self._btn_left    = self._dpad_button("◄")
        self._btn_right   = self._dpad_button("►")
        self._btn_stop    = self._dpad_button("■")
        self._btn_stop.setObjectName("btn_stop_center")

        dpad.addWidget(self._btn_forward, 0, 1, Qt.AlignmentFlag.AlignCenter)
        dpad.addWidget(self._btn_left,    1, 0, Qt.AlignmentFlag.AlignCenter)
        dpad.addWidget(self._btn_stop,    1, 1, Qt.AlignmentFlag.AlignCenter)
        dpad.addWidget(self._btn_right,   1, 2, Qt.AlignmentFlag.AlignCenter)
        dpad.addWidget(self._btn_back,    2, 1, Qt.AlignmentFlag.AlignCenter)

        self._btn_forward.pressed.connect(lambda: self._send_manual(0.3, 0))
        self._btn_back.pressed.connect(lambda: self._send_manual(-0.3, 0))
        self._btn_left.pressed.connect(lambda: self._send_manual(0, -0.3))
        self._btn_right.pressed.connect(lambda: self._send_manual(0, 0.3))
        for btn in [self._btn_forward, self._btn_back,
                    self._btn_left, self._btn_right]:
            btn.released.connect(lambda: self._send_manual(0, 0))
        self._btn_stop.clicked.connect(lambda: self._send_manual(0, 0))

        dpad_outer.addStretch()
        dpad_outer.addLayout(dpad)
        dpad_outer.addStretch()
        layout.addLayout(dpad_outer)

        # ── Height slider ──────────────────────────────────────────────────────
        height_row = QHBoxLayout()
        h_lbl = QLabel("Height:")
        h_lbl.setObjectName("value_small")
        self._height_slider = QSlider(Qt.Orientation.Horizontal)
        self._height_slider.setRange(10, 150)   # 0.1m – 1.5m (×100)
        self._height_slider.setValue(40)
        self._height_slider.valueChanged.connect(self._on_height_changed)
        self._height_val_lbl = QLabel("0.40 m")
        self._height_val_lbl.setObjectName("value_small")
        self._height_val_lbl.setFixedWidth(50)
        height_row.addWidget(h_lbl)
        height_row.addWidget(self._height_slider)
        height_row.addWidget(self._height_val_lbl)
        layout.addLayout(height_row)

        # ── Arm / Disarm ───────────────────────────────────────────────────────
        arm_row = QHBoxLayout()
        arm_row.setSpacing(8)
        self._btn_arm = QPushButton("ARM")
        self._btn_arm.setFixedHeight(32)
        self._btn_arm.setObjectName("btn_connect")
        self._btn_arm.clicked.connect(lambda: self.arm_requested.emit(True))
        self._btn_disarm = QPushButton("DISARM")
        self._btn_disarm.setFixedHeight(32)
        self._btn_disarm.clicked.connect(lambda: self.arm_requested.emit(False))
        arm_row.addWidget(self._btn_arm)
        arm_row.addWidget(self._btn_disarm)
        layout.addLayout(arm_row)

        # ── Emergency Stop ─────────────────────────────────────────────────────
        self._btn_emergency = QPushButton("⚠  EMERGENCY STOP")
        self._btn_emergency.setObjectName("btn_emergency")
        self._btn_emergency.setFixedHeight(44)
        self._btn_emergency.clicked.connect(self.emergency_stop_requested.emit)
        layout.addWidget(self._btn_emergency)

        root.addWidget(card)

    def _dpad_button(self, text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedSize(52, 52)
        btn.setObjectName("btn_dpad")
        # No inline style — inherits from global stylesheet so theme switches work
        return btn

    def _on_connect_click(self) -> None:
        if self._connected:
            self.disconnect_requested.emit()
        else:
            self.connect_requested.emit()

    def _set_mode(self, mode: str) -> None:
        self._mode = mode
        if mode == "MANUAL":
            self._btn_manual.setObjectName("btn_active")
            self._btn_auto.setObjectName("")
        else:
            self._btn_auto.setObjectName("btn_active")
            self._btn_manual.setObjectName("")
        for btn in [self._btn_manual, self._btn_auto]:
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.mode_changed.emit(mode)

    def _on_height_changed(self, value: int) -> None:
        self._target_height = value / 100.0
        self._height_val_lbl.setText(f"{self._target_height:.2f} m")

    def _send_manual(self, vx: float, vy: float) -> None:
        self.manual_command.emit(vx, vy, 0.0, self._target_height)

    @pyqtSlot(bool)
    def set_connected(self, connected: bool) -> None:
        self._connected = connected
        self._conn_badge.set_active(connected)
        self._conn_badge.set_label("CONNECTED" if connected else "DISCONNECTED")
        self._btn_connect.setText("DISCONNECT" if connected else "CONNECT")
        if connected:
            self._btn_connect.setObjectName("btn_active")
        else:
            self._btn_connect.setObjectName("btn_connect")
        self._btn_connect.style().unpolish(self._btn_connect)
        self._btn_connect.style().polish(self._btn_connect)
