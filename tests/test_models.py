import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from models.drone_state import DroneState
from models.tracking_data import TrackingData
from models.security_event import SecurityEvent

def test_drone_state_defaults():
    s = DroneState()
    assert s.connected is False
    assert s.battery_voltage == 0.0
    assert s.battery_percent == 0.0
    assert s.pitch == 0.0
    assert s.roll == 0.0
    assert s.yaw == 0.0
    assert s.height == 0.0
    assert s.motor_m1 == 0
    assert s.motor_m2 == 0
    assert s.motor_m3 == 0
    assert s.motor_m4 == 0
    assert s.velocity_x == 0.0
    assert s.velocity_y == 0.0
    assert s.delta_x == 0.0
    assert s.delta_y == 0.0

def test_drone_state_battery_percent_field():
    s = DroneState(battery_voltage=3.6, battery_percent=50.0)
    assert s.battery_percent == 50.0

def test_tracking_data_defaults():
    t = TrackingData()
    assert t.person_detected is False
    assert t.bbox == (0, 0, 0, 0)
    assert t.center_x == 0
    assert t.center_y == 0
    assert t.confidence == 0.0
    assert t.distance_estimate == 0.0
    assert t.frame_fps == 0.0
    assert t.cmd_vx == 0.0
    assert t.cmd_vy == 0.0

def test_security_event_defaults():
    e = SecurityEvent()
    assert e.event_type == ""
    assert e.verdict == ""
    assert e.token_valid is False
    assert isinstance(e.command_payload, dict)

def test_security_event_fields():
    e = SecurityEvent(
        event_type="REPLAY_ATTACK",
        verdict="DROPPED",
        token_valid=False,
        details="nonce reused"
    )
    assert e.event_type == "REPLAY_ATTACK"
    assert e.verdict == "DROPPED"
    assert e.details == "nonce reused"
