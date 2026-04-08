"""
FlightPage — Live flight dashboard.

4-column × 2-row grid of the core flight panels:
  camera | map | tracking | telemetry
  drone  | mission | system | (spare)

Wrapped in a QScrollArea so panels never shrink below their minimum sizes.
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QFrame,
                              QScrollArea, QSizePolicy)
from PyQt6.QtCore import Qt

from ui.panels.camera_panel import CameraPanel
from ui.panels.drone_panel import DroneControlPanel
from ui.panels.telemetry_panel import TelemetryPanel
from ui.panels.tracking_panel import TrackingPanel
from ui.panels.system_panel import SystemPanel
from ui.panels.map_panel import MapPanel
from ui.panels.mission_panel import MissionPanel


class FlightPage(QWidget):
    """Live flight control and camera view — scrollable."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Scroll area ───────────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        # Inner container — wide enough to prevent shrinking below readable size
        container = QWidget()
        container.setMinimumSize(1400, 800)
        grid = QGridLayout(container)
        grid.setContentsMargins(10, 10, 10, 10)
        grid.setSpacing(8)

        self.camera_panel    = CameraPanel()
        self.map_panel       = MapPanel()
        self.tracking_panel  = TrackingPanel()
        self.telemetry_panel = TelemetryPanel()
        self.drone_panel     = DroneControlPanel()
        self.mission_panel   = MissionPanel()
        self.system_panel    = SystemPanel()

        # Enforce minimum column widths so panels don't collapse
        self.camera_panel.setMinimumWidth(300)
        self.map_panel.setMinimumWidth(280)
        self.tracking_panel.setMinimumWidth(280)
        self.telemetry_panel.setMinimumWidth(280)
        self.drone_panel.setMinimumWidth(260)
        self.mission_panel.setMinimumWidth(260)
        self.system_panel.setMinimumWidth(400)

        # Enforce minimum row heights
        self.camera_panel.setMinimumHeight(340)
        self.map_panel.setMinimumHeight(340)
        self.tracking_panel.setMinimumHeight(340)
        self.telemetry_panel.setMinimumHeight(340)
        self.drone_panel.setMinimumHeight(260)
        self.mission_panel.setMinimumHeight(260)
        self.system_panel.setMinimumHeight(260)

        # Row 0: camera | map | tracking | telemetry
        grid.addWidget(self.camera_panel,    0, 0)
        grid.addWidget(self.map_panel,       0, 1)
        grid.addWidget(self.tracking_panel,  0, 2)
        grid.addWidget(self.telemetry_panel, 0, 3)

        # Row 1: drone | mission | system (span 2 cols)
        grid.addWidget(self.drone_panel,   1, 0)
        grid.addWidget(self.mission_panel, 1, 1)
        grid.addWidget(self.system_panel,  1, 2, 1, 2)

        for col in range(4):
            grid.setColumnStretch(col, 1)
        grid.setRowStretch(0, 3)
        grid.setRowStretch(1, 2)

        scroll.setWidget(container)
        root.addWidget(scroll)
