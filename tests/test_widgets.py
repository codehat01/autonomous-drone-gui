import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)

from ui.widgets.status_badge import StatusBadge
from ui.widgets.led_indicator import LedIndicator
from ui.widgets.gauge_widget import GaugeWidget
from ui.widgets.compass_widget import CompassWidget
from ui.widgets.map_widget import MapWidget

def test_status_badge_instantiates():
    w = StatusBadge("Connected", active=True)
    assert w is not None

def test_status_badge_set_active():
    w = StatusBadge("Test", active=False)
    w.set_active(True)   # should not raise

def test_led_indicator_instantiates():
    w = LedIndicator(color="#00d4aa")
    assert w is not None

def test_led_set_state():
    w = LedIndicator(color="#00d4aa")
    w.set_state(True)
    w.set_state(False)

def test_gauge_widget_instantiates():
    w = GaugeWidget(label="Battery", unit="%", min_val=0, max_val=100)
    assert w is not None

def test_gauge_set_value():
    w = GaugeWidget(label="Battery", unit="%", min_val=0, max_val=100)
    w.set_value(75.0)  # should not raise

def test_compass_widget_instantiates():
    w = CompassWidget()
    assert w is not None

def test_compass_set_heading():
    w = CompassWidget()
    w.set_heading(180.0)  # should not raise

def test_map_widget_instantiates():
    w = MapWidget()
    assert w is not None

def test_map_widget_add_position():
    w = MapWidget()
    w.add_position(1.0, 0.5)  # should not raise

def test_map_widget_reset():
    w = MapWidget()
    w.add_position(1.0, 0.5)
    w.reset_position()  # should not raise
