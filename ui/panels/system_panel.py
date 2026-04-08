import pyqtgraph as pg
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                              QLabel, QProgressBar, QFrame)
from PyQt6.QtCore import pyqtSlot
from utils.theme import COLORS, card_style


class SystemPanel(QWidget):
    """System health: CPU%, RAM%, latency, FPS, signal strength."""

    HISTORY = 60

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lat_hist = [0.0] * self.HISTORY
        self._cpu_hist = [0.0] * self.HISTORY
        self._setup_ui()

    def _stat_row(self, label: str, color: str) -> tuple:
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setObjectName("value_small")
        lbl.setFixedWidth(70)
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setFixedHeight(14)
        bar.setStyleSheet(
            f"QProgressBar::chunk {{ background-color: {color}; border-radius: 3px; }}")
        val = QLabel("--")
        val.setObjectName("value_small")
        val.setFixedWidth(40)
        row.addWidget(lbl)
        row.addWidget(bar)
        row.addWidget(val)
        return row, val, bar

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setStyleSheet(card_style())
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("SYSTEM STATUS")
        title.setObjectName("panel_title")
        layout.addWidget(title)

        big_row = QHBoxLayout()
        self._fps_lbl     = self._big_metric("FPS",     COLORS['accent_teal'])
        self._latency_lbl = self._big_metric("LATENCY", COLORS['accent_amber'])
        big_row.addWidget(self._fps_lbl[0])
        big_row.addWidget(self._latency_lbl[0])
        layout.addLayout(big_row)

        cpu_row, self._cpu_val, self._cpu_bar = self._stat_row("CPU", COLORS['accent_purple'])
        ram_row, self._ram_val, self._ram_bar = self._stat_row("RAM", COLORS['accent_teal'])
        layout.addLayout(cpu_row)
        layout.addLayout(ram_row)

        sig_row = QHBoxLayout()
        sig_lbl = QLabel("Signal:")
        sig_lbl.setObjectName("value_small")
        self._signal_val = QLabel("--")
        self._signal_val.setObjectName("value_small")
        sig_row.addWidget(sig_lbl)
        sig_row.addWidget(self._signal_val)
        sig_row.addStretch()
        layout.addLayout(sig_row)

        self._lat_plot = pg.PlotWidget(title="Latency (ms)")
        self._lat_plot.setBackground(COLORS['bg_card'])
        self._lat_plot.setMaximumHeight(80)
        self._lat_plot.showGrid(x=False, y=True, alpha=0.2)
        self._lat_plot.getPlotItem().getAxis('left').setTextPen(COLORS['text_secondary'])
        self._lat_plot.getPlotItem().getAxis('bottom').setTextPen(COLORS['text_secondary'])
        self._lat_curve = self._lat_plot.plot(
            pen=pg.mkPen(COLORS['accent_amber'], width=2))
        layout.addWidget(self._lat_plot)

        root.addWidget(card)

    def _big_metric(self, label: str, color: str) -> tuple:
        frame = QFrame()
        # Use border-radius only; background inherits from theme stylesheet
        frame.setStyleSheet(
            f"QFrame {{ border: 1px solid {COLORS['border']}; border-radius: 8px; padding: 4px; }}")
        inner = QVBoxLayout(frame)
        inner.setContentsMargins(8, 6, 8, 6)
        lbl = QLabel(label)
        lbl.setObjectName("value_small")
        val = QLabel("--")
        val.setObjectName("value_large")
        val.setStyleSheet(f"color: {color}; font-size: 22px;")
        inner.addWidget(lbl)
        inner.addWidget(val)
        return frame, val

    @pyqtSlot(float, float, float)
    def set_stats(self, cpu: float, ram: float, latency_ms: float) -> None:
        self._cpu_bar.setValue(int(cpu))
        self._cpu_val.setText(f"{cpu:.0f}%")
        self._ram_bar.setValue(int(ram))
        self._ram_val.setText(f"{ram:.0f}%")

        self._lat_hist.pop(0)
        self._lat_hist.append(latency_ms)
        self._lat_curve.setData(self._lat_hist)

        lat_color = (COLORS['accent_green'] if latency_ms < 20
                     else COLORS['accent_amber'] if latency_ms < 50
                     else COLORS['accent_red'])
        self._latency_lbl[1].setText(f"{latency_ms:.0f}ms")
        self._latency_lbl[1].setStyleSheet(f"color: {lat_color}; font-size: 22px;")

        if latency_ms < 20:
            self._signal_val.setText("Excellent")
            self._signal_val.setStyleSheet(f"color: {COLORS['accent_green']};")
        elif latency_ms < 50:
            self._signal_val.setText("Good")
            self._signal_val.setStyleSheet(f"color: {COLORS['accent_amber']};")
        else:
            self._signal_val.setText("Poor")
            self._signal_val.setStyleSheet(f"color: {COLORS['accent_red']};")

    @pyqtSlot(float)
    def set_fps(self, fps: float) -> None:
        self._fps_lbl[1].setText(f"{fps:.1f}")
