import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from security.token_manager import TokenManager
from security.replay_detector import ReplayDetector
from security.command_validator import CommandValidator


# ── TokenManager ─────────────────────────────────────────────────────────────

def test_token_generate_and_verify():
    tm = TokenManager(secret=b"test-key")
    payload = b"vx=0.1,vy=0.0,h=0.4"
    token = tm.generate(payload)
    assert tm.verify(payload, token)


def test_token_wrong_payload_rejected():
    tm = TokenManager(secret=b"test-key")
    token = tm.generate(b"vx=0.1")
    assert not tm.verify(b"vx=0.9", token)


def test_token_wrong_key_rejected():
    tm1 = TokenManager(secret=b"key-A")
    tm2 = TokenManager(secret=b"key-B")
    token = tm1.generate(b"payload")
    assert not tm2.verify(b"payload", token)


# ── ReplayDetector ────────────────────────────────────────────────────────────

def test_replay_fresh_nonce_accepted():
    rd = ReplayDetector(window_seconds=5.0)
    assert not rd.is_replay("nonce-001", time.time())


def test_replay_duplicate_nonce_rejected():
    rd = ReplayDetector(window_seconds=5.0)
    ts = time.time()
    assert not rd.is_replay("nonce-abc", ts)
    assert rd.is_replay("nonce-abc", ts)


def test_replay_stale_timestamp_rejected():
    rd = ReplayDetector(window_seconds=5.0, max_age_seconds=5.0)
    old_ts = time.time() - 10.0
    assert rd.is_replay("nonce-old", old_ts)


def test_replay_future_timestamp_rejected():
    rd = ReplayDetector(window_seconds=5.0, min_age_seconds=2.0)
    future_ts = time.time() + 10.0
    assert rd.is_replay("nonce-future", future_ts)


def test_replay_different_nonces_accepted():
    rd = ReplayDetector(window_seconds=5.0)
    ts = time.time()
    assert not rd.is_replay("nonce-1", ts)
    assert not rd.is_replay("nonce-2", ts)


# ── CommandValidator ──────────────────────────────────────────────────────────

def test_validator_valid_command():
    cv = CommandValidator(max_speed=0.4, max_height=1.5, min_height=0.05)
    ok, msg = cv.validate(0.2, 0.1, 0.4)
    assert ok
    assert msg == "OK"


def test_validator_vx_too_fast():
    cv = CommandValidator(max_speed=0.4)
    ok, msg = cv.validate(0.9, 0.0, 0.4)
    assert not ok
    assert "vx" in msg


def test_validator_vy_too_fast():
    cv = CommandValidator(max_speed=0.4)
    ok, msg = cv.validate(0.0, -0.9, 0.4)
    assert not ok
    assert "vy" in msg


def test_validator_height_too_high():
    cv = CommandValidator(max_height=1.5)
    ok, msg = cv.validate(0.0, 0.0, 2.0)
    assert not ok
    assert "height" in msg


def test_validator_height_too_low():
    cv = CommandValidator(min_height=0.05)
    ok, msg = cv.validate(0.0, 0.0, 0.01)
    assert not ok
    assert "height" in msg


if __name__ == "__main__":
    tests = [
        test_token_generate_and_verify,
        test_token_wrong_payload_rejected,
        test_token_wrong_key_rejected,
        test_replay_fresh_nonce_accepted,
        test_replay_duplicate_nonce_rejected,
        test_replay_stale_timestamp_rejected,
        test_replay_future_timestamp_rejected,
        test_replay_different_nonces_accepted,
        test_validator_valid_command,
        test_validator_vx_too_fast,
        test_validator_vy_too_fast,
        test_validator_height_too_high,
        test_validator_height_too_low,
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
