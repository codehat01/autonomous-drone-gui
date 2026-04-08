import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)

from utils.theme import get_main_stylesheet, COLORS, card_style

def test_stylesheet_is_nonempty_string():
    css = get_main_stylesheet()
    assert isinstance(css, str)
    assert len(css) > 100

def test_stylesheet_contains_key_selectors():
    css = get_main_stylesheet()
    assert "QMainWindow" in css
    assert "QPushButton" in css
    assert "QProgressBar" in css

def test_colors_dict_has_required_keys():
    required = [
        'bg_primary', 'bg_card', 'accent_teal', 'accent_red',
        'accent_green', 'text_primary', 'border', 'emergency_red'
    ]
    for key in required:
        assert key in COLORS, f"Missing color key: {key}"

def test_colors_are_valid_hex():
    for key, val in COLORS.items():
        assert val.startswith('#'), f"Color {key}={val} is not hex"
        assert len(val) in (4, 7), f"Color {key}={val} invalid hex length"

def test_card_style_nonempty():
    s = card_style()
    assert isinstance(s, str)
    assert "background-color" in s
    assert "border-radius" in s
