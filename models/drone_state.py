from dataclasses import dataclass, field


@dataclass
class DroneState:
    connected: bool = False
    battery_voltage: float = 0.0       # pm.vbat in Volts
    battery_percent: float = 0.0       # (vbat - 3.0) / (4.2 - 3.0) * 100
    pitch: float = 0.0                 # stateEstimate.pitch degrees
    roll: float = 0.0                  # stateEstimate.roll degrees
    yaw: float = 0.0                   # stateEstimate.yaw degrees
    height: float = 0.0               # stateEstimate.z meters
    motor_m1: int = 0                  # pwm.m1_pwm 0-60000
    motor_m2: int = 0
    motor_m3: int = 0
    motor_m4: int = 0
    velocity_x: float = 0.0           # derived from optical flow m/s
    velocity_y: float = 0.0
    delta_x: float = 0.0              # motion.deltaX raw
    delta_y: float = 0.0              # motion.deltaY raw
    timestamp: float = 0.0
