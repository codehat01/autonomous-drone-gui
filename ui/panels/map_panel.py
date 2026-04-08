from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                              QLabel, QPushButton, QFrame)
from PyQt6.QtCore import pyqtSlot
from utils.theme import COLORS, card_style
from utils.config import VELOCITY_CONSTANT, DT
from ui.widgets.map_widget import MapWidget
from models.drone_state import DroneState


class MapPanel(QWidget):
    """
    Indoor dead-reckoning position map panel.
    Wraps MapWidget with header, reset button, and live coordinate readout.
    Position is accumulated from DroneState.delta_x/delta_y + height.
    Velocity constant from test_optical_flow_sensor.py:
        (5.4° * DEG_TO_RAD) / (30 pixels * DT)
    """

    _VEL_CONST = VELOCITY_CONSTANT   # (5.4° in rad) / (30 pixels × 0.01s)
    _DT        = DT                   # 0.01 s (SENSOR_PERIOD_MS=10)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pos_x = 0.0
        self._pos_y = 0.0
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setStyleSheet(card_style())
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("INDOOR POSITION TRACKER")
        title.setObjectName("panel_title")
        sublabel = QLabel("Dead Reckoning  |  Optical Flow + ToF")
        sublabel.setObjectName("value_small")
        self._reset_btn = QPushButton("RESET ORIGIN")
        self._reset_btn.setFixedHeight(26)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self._reset_btn)
        layout.addLayout(header)
        layout.addWidget(sublabel)

        self._map = MapWidget()
        layout.addWidget(self._map, stretch=1)

        self._reset_btn.clicked.connect(self._on_reset)

        root.addWidget(card)

    def _on_reset(self) -> None:
        self._pos_x = 0.0
        self._pos_y = 0.0
        self._map.reset_position()

    @pyqtSlot(object)   # DroneState
    def set_state(self, state: DroneState) -> None:
        if state.height < 0.05:
            return  # ignore ground-level noise
        # Velocity calculation from test_optical_flow_sensor.py:
        #   velocity = delta * altitude * velocity_constant
        vx = state.delta_x * state.height * self._VEL_CONST
        vy = state.delta_y * state.height * self._VEL_CONST
        self._pos_x += vx * self._DT
        self._pos_y += vy * self._DT
        self._map.add_position(self._pos_x, self._pos_y)
        self._map.set_heading(state.yaw)
