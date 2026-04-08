from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt
from utils.theme import COLORS


class StatusBadge(QWidget):
    """Colored dot + label showing a named status (active/inactive)."""

    def __init__(self, label: str, active: bool = False, parent=None):
        super().__init__(parent)
        self._label_text = label
        self._active = active

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)

        self._dot = QLabel("●")
        self._dot.setFixedSize(14, 14)
        self._dot.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._text = QLabel(label)
        self._text.setObjectName("value_small")

        layout.addWidget(self._dot)
        layout.addWidget(self._text)

        self._update_style()

    def set_active(self, active: bool) -> None:
        self._active = active
        self._update_style()

    def set_label(self, label: str) -> None:
        self._label_text = label
        self._text.setText(label)

    def _update_style(self) -> None:
        color = COLORS['accent_green'] if self._active else COLORS['accent_red']
        self._dot.setStyleSheet(f"color: {color}; font-size: 10px;")
