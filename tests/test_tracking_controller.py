import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from controllers.tracking_controller import TrackingController
from models.tracking_data import TrackingData


def _make(detected=True, cx=320, cy=240, bbox=(220, 100, 420, 380)):
    return TrackingData(
        person_detected=detected,
        bbox=bbox,
        center_x=cx,
        center_y=cy,
        confidence=0.9,
        distance_estimate=2.0,
        frame_fps=30.0,
        cmd_vx=0.0,
        cmd_vy=0.0,
    )


def test_no_detection_returns_zero():
    tc = TrackingController(frame_w=640, frame_h=480)
    vx, vy = tc.compute(_make(detected=False))
    assert vx == 0.0 and vy == 0.0


def test_centered_person_near_zero():
    tc = TrackingController(frame_w=640, frame_h=480)
    # bbox height = 192px, target = 0.4*480 = 192 → depth error = 0
    vx, vy = tc.compute(_make(cx=320, cy=240, bbox=(224, 144, 416, 336)))
    assert abs(vy) < 0.01  # centered laterally
    assert abs(vx) < 0.05  # near target depth


def test_person_right_gives_positive_vy():
    tc = TrackingController(frame_w=640, frame_h=480)
    vx, vy = tc.compute(_make(cx=500, cy=240))  # person right of center
    assert vy > 0.0


def test_person_left_gives_negative_vy():
    tc = TrackingController(frame_w=640, frame_h=480)
    vx, vy = tc.compute(_make(cx=100, cy=240))  # person left of center
    assert vy < 0.0


def test_output_clamped_to_max_speed():
    tc = TrackingController(frame_w=640, frame_h=480, max_speed=0.4)
    # Extreme offset
    vx, vy = tc.compute(_make(cx=639, cy=240, bbox=(0, 0, 640, 480)))
    assert abs(vx) <= 0.4
    assert abs(vy) <= 0.4


if __name__ == "__main__":
    tests = [
        test_no_detection_returns_zero,
        test_centered_person_near_zero,
        test_person_right_gives_positive_vy,
        test_person_left_gives_negative_vy,
        test_output_clamped_to_max_speed,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
    print(f"\n{passed}/{len(tests)} tests passed")
