"""
ConnectPage — Drone connection wizard page.

Derived directly from:
  - simple_drone_connection_test.py  (initialize_drone / terminate_drone)
  - hellow_litewing.py               (open_link, safety unlock, send_setpoint)
  - battery_voltage_read.py          (pm.vbat LogConfig, voltage_callback)
  - ToF-Read.py                      (stateEstimate.z LogConfig, tof_callback)
  - simple_para_read.py              (TOC dump, list controller params)

Shows:
  - URI input + Connect / Disconnect buttons
  - Connection status LED + console log
  - Live battery voltage (pm.vbat)
  - Live ToF height (stateEstimate.z)
  - TOC variable browser (lists all drone parameters)
  - Safety unlock button (send_setpoint 0,0,0,0)
  - High-level commander toggle (commander.enHighLevel)
  - CRTP packet counter (Sent / Received)
"""
import time

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QFrame,
    QTextEdit, QProgressBar, QSplitter, QListWidget,
    QListWidgetItem, QGroupBox, QScrollArea,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont

from utils.theme import COLORS, card_style, FONT_MONO
from ui.widgets.status_badge import StatusBadge
from ui.widgets.led_indicator import LedIndicator
from utils.config import DRONE_URI


class ConnectPage(QWidget):
    """
    Full-page drone connection wizard.
    Emits connect_requested(uri) / disconnect_requested() for the controller.
    Also handles direct low-level connection tests matching the Python-Scripts.
    """

    connect_requested    = pyqtSignal(str)    # uri
    disconnect_requested = pyqtSignal()
    arm_requested        = pyqtSignal()       # safety unlock: send_setpoint(0,0,0,0)
    high_level_requested = pyqtSignal(bool)   # commander.enHighLevel
    neopixel_requested   = pyqtSignal(str, int, int, int)  # action, r, g, b

    def __init__(self, parent=None):
        super().__init__(parent)
        self._connected = False
        self._packets_sent = 0
        self._packets_recv = 0
        self._setup_ui()

    # ── UI build ─────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        _inner = QWidget()
        _inner.setMinimumWidth(900)
        outer.addWidget(scroll)
        scroll.setWidget(_inner)

        root = QVBoxLayout(_inner)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # ── Page title ──────────────────────────────────────────────────────
        title_row = QHBoxLayout()
        page_title = QLabel("DRONE CONNECTION  &  DIAGNOSTICS")
        page_title.setObjectName("connect_page_title")
        title_row.addWidget(page_title)
        title_row.addStretch()
        sub = QLabel("NanoHawk  ·  CRTP over UDP WiFi  ·  cflib")
        sub.setObjectName("value_small")
        title_row.addWidget(sub)
        root.addLayout(title_row)

        # ── Main 2-column split ─────────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left column
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(10)

        left_layout.addWidget(self._build_connection_card())
        left_layout.addWidget(self._build_sensor_card())
        left_layout.addWidget(self._build_control_card())
        left_layout.addWidget(self._build_neopixel_card())
        left_layout.addStretch()

        # Right column — console + TOC browser
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(10)
        right_layout.addWidget(self._build_console_card())
        right_layout.addWidget(self._build_toc_card())

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([520, 680])
        root.addWidget(splitter, stretch=1)

    # ── Cards ─────────────────────────────────────────────────────────────────

    def _build_connection_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(card_style())
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        h = QHBoxLayout()
        t = QLabel("CONNECTION")
        t.setObjectName("panel_title")
        h.addWidget(t)
        h.addStretch()
        self._conn_led = LedIndicator()
        self._conn_led.set_state(False)
        h.addWidget(self._conn_led)
        layout.addLayout(h)

        # URI row — matches DRONE_URI pattern from all scripts
        uri_row = QHBoxLayout()
        uri_lbl = QLabel("Drone URI:")
        uri_lbl.setObjectName("value_small")
        uri_lbl.setFixedWidth(80)
        self._uri_input = QLineEdit(DRONE_URI)
        self._uri_input.setPlaceholderText("udp://192.168.43.42:2390")
        self._uri_input.setFont(QFont(FONT_MONO.split(",")[0].strip(), 11))
        self._uri_input.setObjectName("uri_input")
        uri_row.addWidget(uri_lbl)
        uri_row.addWidget(self._uri_input)
        layout.addLayout(uri_row)

        # Status badge
        badge_row = QHBoxLayout()
        status_lbl = QLabel("Status:")
        status_lbl.setObjectName("value_small")
        status_lbl.setFixedWidth(80)
        self._status_badge = StatusBadge("DISCONNECTED", active=False)
        badge_row.addWidget(status_lbl)
        badge_row.addWidget(self._status_badge)
        badge_row.addStretch()
        layout.addLayout(badge_row)

        # Buttons — connect / disconnect  (matches simple_drone_connection_test.py)
        btn_row = QHBoxLayout()
        self._btn_connect = QPushButton("⚡  CONNECT")
        self._btn_connect.setObjectName("btn_connect")
        self._btn_connect.setFixedHeight(40)
        self._btn_connect.clicked.connect(self._on_connect_clicked)

        self._btn_disconnect = QPushButton("✕  DISCONNECT")
        self._btn_disconnect.setFixedHeight(40)
        self._btn_disconnect.setEnabled(False)
        self._btn_disconnect.clicked.connect(self._on_disconnect_clicked)

        btn_row.addWidget(self._btn_connect)
        btn_row.addWidget(self._btn_disconnect)
        layout.addLayout(btn_row)

        # Packet counters (from battery_voltage_read.py packet logger)
        pkt_row = QHBoxLayout()
        self._sent_lbl  = QLabel("Sent: 0 pkts")
        self._recv_lbl  = QLabel("Recv: 0 pkts")
        self._sent_lbl.setObjectName("value_small")
        self._recv_lbl.setObjectName("value_small")
        pkt_row.addWidget(self._sent_lbl)
        pkt_row.addWidget(self._recv_lbl)
        pkt_row.addStretch()
        layout.addLayout(pkt_row)

        return card

    def _build_sensor_card(self) -> QFrame:
        """Battery + ToF height — from battery_voltage_read.py and ToF-Read.py."""
        card = QFrame()
        card.setStyleSheet(card_style())
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        t = QLabel("LIVE SENSOR READINGS")
        t.setObjectName("panel_title")
        layout.addWidget(t)

        grid = QGridLayout()
        grid.setSpacing(10)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        # Battery voltage — pm.vbat (battery_voltage_read.py)
        batt_lbl = QLabel("Battery (pm.vbat):")
        batt_lbl.setObjectName("value_small")
        self._batt_val = QLabel("--  V")
        self._batt_val.setObjectName("sensor_val_green")
        self._batt_bar = QProgressBar()
        self._batt_bar.setRange(300, 420)   # 3.0V–4.2V * 100
        self._batt_bar.setValue(300)
        self._batt_bar.setFixedHeight(10)
        self._batt_bar.setTextVisible(False)
        self._batt_bar.setObjectName("batt_bar")

        # ToF height — stateEstimate.z (ToF-Read.py)
        tof_lbl = QLabel("Height (stateEstimate.z):")
        tof_lbl.setObjectName("value_small")
        self._tof_val = QLabel("--  m")
        self._tof_val.setObjectName("sensor_val_teal")
        self._tof_bar = QProgressBar()
        self._tof_bar.setRange(0, 150)   # 0–1.5m * 100
        self._tof_bar.setValue(0)
        self._tof_bar.setFixedHeight(10)
        self._tof_bar.setTextVisible(False)
        self._tof_bar.setObjectName("tof_bar")

        grid.addWidget(batt_lbl,      0, 0)
        grid.addWidget(self._batt_val, 0, 1)
        grid.addWidget(self._batt_bar, 1, 0, 1, 2)
        grid.addWidget(tof_lbl,       2, 0)
        grid.addWidget(self._tof_val,  2, 1)
        grid.addWidget(self._tof_bar,  3, 0, 1, 2)
        layout.addLayout(grid)

        return card

    def _build_control_card(self) -> QFrame:
        """Safety unlock + high-level commander — from hellow_litewing.py / zrange_read.py."""
        card = QFrame()
        card.setStyleSheet(card_style())
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        t = QLabel("DRONE CONTROL PRIMITIVES")
        t.setObjectName("panel_title")
        layout.addWidget(t)

        info = QLabel(
            "Safety unlock sends send_setpoint(0,0,0,0) — required before any flight command.\n"
            "High-level mode sets commander.enHighLevel=1 to enable hover_setpoint.")
        info.setObjectName("value_small")
        info.setWordWrap(True)
        layout.addWidget(info)

        btn_row = QHBoxLayout()

        # Safety unlock — matches hellow_litewing.py line 27
        self._btn_arm = QPushButton("🔓  SAFETY UNLOCK")
        self._btn_arm.setFixedHeight(36)
        self._btn_arm.setEnabled(False)
        self._btn_arm.setObjectName("btn_safety_unlock")
        self._btn_arm.clicked.connect(self.arm_requested.emit)

        # High-level commander — matches zrange_read.py line 87
        self._btn_hli = QPushButton("⚙  ENABLE HIGH-LEVEL")
        self._btn_hli.setFixedHeight(36)
        self._btn_hli.setEnabled(False)
        self._btn_hli.setObjectName("btn_high_level")
        self._btn_hli.clicked.connect(lambda: self.high_level_requested.emit(True))

        btn_row.addWidget(self._btn_arm)
        btn_row.addWidget(self._btn_hli)
        layout.addLayout(btn_row)

        return card

    def _build_neopixel_card(self) -> QFrame:
        """
        NeoPixel LED control — dead-reckoning-maneuvers.py CRTP port 0x09.
        Buttons emit neopixel_requested(action, r, g, b).
        Actions: 'set_all', 'clear', 'blink_start', 'blink_stop'
        """
        card = QFrame()
        card.setStyleSheet(card_style())
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        t = QLabel("NEOPIXEL LED CONTROL  (CRTP port 0x09)")
        t.setObjectName("panel_title")
        layout.addWidget(t)

        info = QLabel(
            "np_set_all(r,g,b) → SET_PIXEL channel (index 0xFF)\n"
            "np_clear() → CLEAR channel  |  np_blink() → BLINK channel")
        info.setObjectName("value_small")
        info.setWordWrap(True)
        layout.addWidget(info)

        # Color preset buttons row
        color_row = QHBoxLayout()
        presets = [
            ("🔴 RED",   (255, 0,   0  )),
            ("🟢 GREEN", (0,   255, 0  )),
            ("🔵 BLUE",  (0,   0,   255)),
            ("🟡 AMBER", (255, 160, 0  )),
            ("⚪ WHITE",  (255, 255, 255)),
        ]
        self._np_btns = []
        for label, (r, g, b) in presets:
            btn = QPushButton(label)
            btn.setFixedHeight(30)
            btn.setEnabled(False)
            btn.clicked.connect(
                lambda checked=False, _r=r, _g=g, _b=b:
                    self.neopixel_requested.emit("set_all", _r, _g, _b))
            color_row.addWidget(btn)
            self._np_btns.append(btn)
        layout.addLayout(color_row)

        # Control row
        ctrl_row = QHBoxLayout()
        self._btn_np_clear = QPushButton("⬛ CLEAR")
        self._btn_np_clear.setFixedHeight(30)
        self._btn_np_clear.setEnabled(False)
        self._btn_np_clear.clicked.connect(
            lambda: self.neopixel_requested.emit("clear", 0, 0, 0))

        self._btn_np_blink = QPushButton("✨ BLINK")
        self._btn_np_blink.setFixedHeight(30)
        self._btn_np_blink.setEnabled(False)
        self._btn_np_blink.clicked.connect(
            lambda: self.neopixel_requested.emit("blink_start", 0, 255, 100))

        self._btn_np_stop = QPushButton("■ STOP BLINK")
        self._btn_np_stop.setFixedHeight(30)
        self._btn_np_stop.setEnabled(False)
        self._btn_np_stop.clicked.connect(
            lambda: self.neopixel_requested.emit("blink_stop", 0, 0, 0))

        ctrl_row.addWidget(self._btn_np_clear)
        ctrl_row.addWidget(self._btn_np_blink)
        ctrl_row.addWidget(self._btn_np_stop)
        layout.addLayout(ctrl_row)

        return card

    def _build_console_card(self) -> QFrame:
        """Console log — matches print() output from all Python-Scripts."""
        card = QFrame()
        card.setStyleSheet(card_style())
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        hdr = QHBoxLayout()
        t = QLabel("CONNECTION LOG")
        t.setObjectName("panel_title")
        hdr.addWidget(t)
        hdr.addStretch()
        clr = QPushButton("CLEAR")
        clr.setFixedHeight(22)
        clr.setFixedWidth(60)
        clr.clicked.connect(lambda: self._console.clear())
        hdr.addWidget(clr)
        layout.addLayout(hdr)

        self._console = QTextEdit()
        self._console.setReadOnly(True)
        self._console.setFont(QFont(FONT_MONO.split(",")[0].strip(), 10))
        self._console.setObjectName("connection_console")
        self._console.setMinimumHeight(260)
        layout.addWidget(self._console, stretch=1)

        self._log("NanoHawk Control Station — Connection Console")
        self._log(f"Default URI: {DRONE_URI}")
        self._log("Ready. Press CONNECT to begin.")

        return card

    def _build_toc_card(self) -> QFrame:
        """TOC variable browser — from simple_para_read.py debug_toc()."""
        card = QFrame()
        card.setStyleSheet(card_style())
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        hdr = QHBoxLayout()
        t = QLabel("DRONE PARAMETER BROWSER  (TOC)")
        t.setObjectName("panel_title")
        hdr.addWidget(t)
        hdr.addStretch()
        self._btn_toc = QPushButton("REFRESH")
        self._btn_toc.setFixedHeight(22)
        self._btn_toc.setFixedWidth(80)
        self._btn_toc.setEnabled(False)
        self._btn_toc.clicked.connect(self.toc_refresh_requested)
        hdr.addWidget(self._btn_toc)
        layout.addLayout(hdr)

        info = QLabel("Lists all available log variables (motion, stateEstimate, pm, pwm, controller…)")
        info.setObjectName("value_small")
        layout.addWidget(info)

        self._toc_list = QListWidget()
        self._toc_list.setObjectName("security_log")
        self._toc_list.setFont(QFont(FONT_MONO.split(",")[0].strip(), 9))
        self._toc_list.setMinimumHeight(180)
        layout.addWidget(self._toc_list, stretch=1)

        return card

    # ── Slots called from controller ─────────────────────────────────────────

    @pyqtSlot()
    def on_connected(self) -> None:
        self._connected = True
        self._status_badge.set_label("CONNECTED")
        self._status_badge.set_active(True)
        self._conn_led.set_state(True)
        self._btn_connect.setEnabled(False)
        self._btn_disconnect.setEnabled(True)
        self._btn_arm.setEnabled(True)
        self._btn_hli.setEnabled(True)
        self._btn_toc.setEnabled(True)
        for btn in self._np_btns:
            btn.setEnabled(True)
        self._btn_np_clear.setEnabled(True)
        self._btn_np_blink.setEnabled(True)
        self._btn_np_stop.setEnabled(True)
        self._log("✓ Connected to drone!")
        self._log("  Safety unlock: press SAFETY UNLOCK")
        self._log("  Then: ENABLE HIGH-LEVEL to use hover_setpoint")

    @pyqtSlot()
    def on_disconnected(self) -> None:
        self._connected = False
        self._status_badge.set_label("DISCONNECTED")
        self._status_badge.set_active(False)
        self._conn_led.set_state(False)
        self._btn_connect.setEnabled(True)
        self._btn_disconnect.setEnabled(False)
        self._btn_arm.setEnabled(False)
        self._btn_hli.setEnabled(False)
        self._btn_toc.setEnabled(False)
        for btn in self._np_btns:
            btn.setEnabled(False)
        self._btn_np_clear.setEnabled(False)
        self._btn_np_blink.setEnabled(False)
        self._btn_np_stop.setEnabled(False)
        self._batt_val.setText("--  V")
        self._tof_val.setText("--  m")
        self._log("✗ Disconnected from drone.")

    @pyqtSlot(str)
    def on_error(self, msg: str) -> None:
        # Status messages (Connecting…, ✓ Connected, etc.) pass through as-is
        # Only messages that look like errors get red color
        is_error = not (msg.startswith("✓") or msg.startswith("Connecting"))
        color = COLORS['accent_red'] if is_error else COLORS['accent_teal']
        self._log(msg, color=color)

    @pyqtSlot(float)
    def set_battery(self, voltage: float) -> None:
        """Called from DroneService battery callback (pm.vbat)."""
        color = (COLORS['accent_green'] if voltage > 3.7
                 else COLORS['accent_amber'] if voltage > 3.5
                 else COLORS['accent_red'])
        self._batt_val.setText(f"{voltage:.2f}  V")
        self._batt_val.setStyleSheet(
            f"color: {color}; font-size: 22px; font-weight: bold; font-family: {FONT_MONO};")
        self._batt_bar.setValue(int(voltage * 100))

    @pyqtSlot(float)
    def set_height(self, height: float) -> None:
        """Called from DroneService ToF callback (stateEstimate.z)."""
        self._tof_val.setText(f"{height:.3f}  m")
        self._tof_bar.setValue(int(height * 100))

    @pyqtSlot(int, int)
    def set_packet_counts(self, sent: int, recv: int) -> None:
        self._sent_lbl.setText(f"Sent: {sent} pkts")
        self._recv_lbl.setText(f"Recv: {recv} pkts")

    @pyqtSlot(list)
    def populate_toc(self, variables: list[str]) -> None:
        """Populate TOC browser — from simple_para_read.py debug_toc()."""
        self._toc_list.clear()
        for var in sorted(variables):
            item = QListWidgetItem(var)
            # Colour-code by group
            group = var.split(".")[0] if "." in var else ""
            if group == "stateEstimate":
                item.setForeground(Qt.GlobalColor.cyan)
            elif group == "pm":
                item.setForeground(Qt.GlobalColor.green)
            elif group == "pwm":
                item.setForeground(Qt.GlobalColor.yellow)
            elif group == "motion":
                item.setForeground(Qt.GlobalColor.magenta)
            elif group == "controller":
                item.setForeground(Qt.GlobalColor.red)
            self._toc_list.addItem(item)
        self._log(f"✓ TOC loaded: {len(variables)} variables")

    def toc_refresh_requested(self) -> None:
        self._log("Requesting TOC refresh…")

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _on_connect_clicked(self) -> None:
        uri = self._uri_input.text().strip() or DRONE_URI
        # Validate URI — udpdriver.py requires a port number
        if uri.startswith("udp://") and ":" not in uri[6:]:
            uri = uri + ":19797"
            self._uri_input.setText(uri)
            self._log(f"⚠ No port specified — using default :19797 → {uri}",
                      color=COLORS['accent_amber'])
        self._log(f"Connecting to {uri}…")
        self._log("  cflib.crtp.init_drivers()")
        self._log(f"  SyncCrazyflie('{uri}', cf=Crazyflie(rw_cache='./cache'))")
        self.connect_requested.emit(uri)

    def _on_disconnect_clicked(self) -> None:
        self._log("Disconnecting…")
        self.disconnect_requested.emit()

    def _log(self, msg: str, color: str = "") -> None:
        if color:
            self._console.append(
                f'<span style="color:{color};">{msg}</span>')
        else:
            self._console.append(msg)
        # Auto-scroll
        sb = self._console.verticalScrollBar()
        sb.setValue(sb.maximum())
