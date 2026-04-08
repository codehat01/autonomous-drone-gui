import pyqtgraph as pg
import numpy as np
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                              QLabel, QPushButton, QFrame)
from PyQt6.QtCore import pyqtSlot
from utils.theme import COLORS, card_style
from models.tracking_data import TrackingData

HISTORY = 300   # ~30s of data


class TrackingPanel(QWidget):
    """
    4 live pyqtgraph plots: X position, Y position, distance estimate, Vx/Vy overlay.
    Updated via set_tracking(TrackingData) slot.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._t = list(range(HISTORY))
        self._x_hist      = [0.0] * HISTORY
        self._y_hist      = [0.0] * HISTORY
        self._dist_hist   = [0.0] * HISTORY
        self._vx_hist     = [0.0] * HISTORY
        self._vy_hist     = [0.0] * HISTORY
        self._setup_ui()

    def _make_plot(self, title: str, y_label: str,
                   color1: str, color2: str = None) -> tuple:
        plot = pg.PlotWidget()
        plot.setBackground(COLORS['bg_card'])
        plot.setTitle(title, color=COLORS['text_secondary'], size="10pt")
        plot.setLabel('left', y_label, color=COLORS['text_secondary'])
        plot.showGrid(x=True, y=True, alpha=0.15)
        plot.getPlotItem().getAxis('bottom').setTextPen(COLORS['text_secondary'])
        plot.getPlotItem().getAxis('left').setTextPen(COLORS['text_secondary'])
        c1 = plot.plot(pen=pg.mkPen(color1, width=2))
        c2 = plot.plot(pen=pg.mkPen(color2, width=2)) if color2 else None
        return plot, c1, c2

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setStyleSheet(card_style())
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # ── Header ─────────────────────────────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel("TRACKING ANALYTICS")
        title.setObjectName("panel_title")
        self._export_btn = QPushButton("EXPORT CSV")
        self._export_btn.setFixedHeight(24)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self._export_btn)
        layout.addLayout(header)

        # ── Live stats row ─────────────────────────────────────────────────────
        stats_row = QHBoxLayout()
        self._conf_lbl    = QLabel("Confidence: --")
        self._dist_lbl    = QLabel("Distance: -- m")
        self._target_lbl  = QLabel("Target: NONE")
        for lbl in [self._conf_lbl, self._dist_lbl, self._target_lbl]:
            lbl.setObjectName("value_small")
            stats_row.addWidget(lbl)
        stats_row.addStretch()
        layout.addLayout(stats_row)

        # ── 2×2 Plot grid — equal column/row stretch ──────────────────────────
        grid = QGridLayout()
        grid.setSpacing(6)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)

        self._plot_x, self._curve_x, _ = self._make_plot(
            "Target X (px)", "X (px)", COLORS['accent_teal'])
        self._plot_y, self._curve_y, _ = self._make_plot(
            "Target Y (px)", "Y (px)", COLORS['accent_purple'])
        self._plot_d, self._curve_d, _ = self._make_plot(
            "Distance Estimate", "Dist (m)", COLORS['accent_amber'])
        self._plot_v, self._curve_vx, self._curve_vy = self._make_plot(
            "Cmd Vx / Vy (m/s)", "Vel (m/s)",
            COLORS['accent_teal'], COLORS['accent_red'])

        grid.addWidget(self._plot_x, 0, 0)
        grid.addWidget(self._plot_y, 0, 1)
        grid.addWidget(self._plot_d, 1, 0)
        grid.addWidget(self._plot_v, 1, 1)
        layout.addLayout(grid)

        root.addWidget(card)

    @pyqtSlot(object)   # TrackingData
    def set_tracking(self, data: TrackingData) -> None:
        self._x_hist.pop(0)
        self._x_hist.append(data.center_x)
        self._y_hist.pop(0)
        self._y_hist.append(data.center_y)
        self._dist_hist.pop(0)
        self._dist_hist.append(data.distance_estimate)
        self._vx_hist.pop(0)
        self._vx_hist.append(data.cmd_vx)
        self._vy_hist.pop(0)
        self._vy_hist.append(data.cmd_vy)

        self._curve_x.setData(self._t, self._x_hist)
        self._curve_y.setData(self._t, self._y_hist)
        self._curve_d.setData(self._t, self._dist_hist)
        self._curve_vx.setData(self._t, self._vx_hist)
        self._curve_vy.setData(self._t, self._vy_hist)

        status = "LOCKED" if data.person_detected else "NONE"
        color = COLORS['accent_green'] if data.person_detected else COLORS['text_secondary']
        self._target_lbl.setText(f"Target: {status}")
        self._target_lbl.setStyleSheet(f"color: {color};")
        self._conf_lbl.setText(f"Confidence: {data.confidence * 100:.0f}%")
        self._dist_lbl.setText(f"Distance: {data.distance_estimate:.2f} m")
