"""
SecurityService — authenticates and validates drone velocity commands
before forwarding them to DroneService.

Pipeline per command:
  1. HMAC-SHA256 token verification          → rejects tampered commands
  2. Nonce + timestamp replay detection      → rejects replayed commands
  3. Range / speed limit validation          → rejects out-of-bounds commands
  4. Forward validated command to DroneService
  5. Emit security event for the UI log

Emits:
    event_emitted(SecurityEvent)   — for SecurityPanel
    command_accepted(float, float, float)  — (vx, vy, height) validated command
    command_blocked(str)           — reason for rejection
"""
import time
import os
import uuid

from PyQt6.QtCore import QObject, pyqtSignal

from security.token_manager import TokenManager
from security.replay_detector import ReplayDetector
from security.command_validator import CommandValidator
from models.security_event import SecurityEvent


def _encode_payload(vx: float, vy: float, height: float, nonce: str, ts: float) -> bytes:
    return f"vx={vx:.4f},vy={vy:.4f},h={height:.4f},nonce={nonce},ts={ts:.6f}".encode()


class SecurityService(QObject):
    """
    Synchronous security pipeline (runs on the caller's thread).
    Wraps TokenManager + ReplayDetector + CommandValidator.

    Use sign_command() to get a token for outgoing commands.
    Use validate_command() to authenticate incoming commands.
    """

    event_emitted     = pyqtSignal(object)          # SecurityEvent
    command_accepted  = pyqtSignal(float, float, float)
    command_blocked   = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        secret = os.environ.get("DRONE_HMAC_SECRET", "nanohawk-default-secret").encode()
        self._tm = TokenManager(secret=secret)
        self._rd = ReplayDetector(window_seconds=5.0)
        self._cv = CommandValidator()

        self._sent_count = 0
        self._blocked_count = 0

    # ── Public API ────────────────────────────────────────────────────────────

    def sign_command(
        self,
        vx: float,
        vy: float,
        height: float,
    ) -> tuple[str, str, float]:
        """
        Signs a command.  Returns (token, nonce, timestamp).
        Call this before sending the command over the network.
        """
        nonce = uuid.uuid4().hex
        ts = time.time()
        payload = _encode_payload(vx, vy, height, nonce, ts)
        token = self._tm.generate(payload)
        return token, nonce, ts

    def validate_command(
        self,
        vx: float,
        vy: float,
        height: float,
        token: str,
        nonce: str,
        timestamp: float,
    ) -> bool:
        """
        Runs the full security pipeline.  Returns True if command is safe to execute.
        Emits event_emitted and either command_accepted or command_blocked.
        """
        payload = _encode_payload(vx, vy, height, nonce, timestamp)
        details = f"vx={vx:.2f} vy={vy:.2f} h={height:.2f}"

        # ── Step 1: HMAC token ──────────────────────────────────────────────
        if not self._tm.verify(payload, token):
            return self._reject("INVALID_TOKEN", "HMAC token mismatch", details)

        # ── Step 2: Replay detection ────────────────────────────────────────
        if self._rd.is_replay(nonce, timestamp):
            return self._reject("REPLAY_ATTACK", "nonce reused within 5s window", details)

        # ── Step 3: Range validation ────────────────────────────────────────
        ok, reason = self._cv.validate(vx, vy, height)
        if not ok:
            return self._reject("INVALID_RANGE", reason, details)

        # ── All checks passed ───────────────────────────────────────────────
        self._sent_count += 1
        event = SecurityEvent(
            event_type="VALID",
            timestamp=time.time(),
            command_payload=details,
            verdict="ALLOWED",
            token_valid=True,
            details=details,
        )
        self.event_emitted.emit(event)
        self.command_accepted.emit(vx, vy, height)
        return True

    def submit_command(
        self,
        vx: float,
        vy: float,
        height: float,
    ) -> bool:
        """
        Convenience: sign + validate in one call (for local commands from UI).
        Returns True if accepted.
        """
        token, nonce, ts = self.sign_command(vx, vy, height)
        return self.validate_command(vx, vy, height, token, nonce, ts)

    @property
    def sent_count(self) -> int:
        return self._sent_count

    @property
    def blocked_count(self) -> int:
        return self._blocked_count

    # ── Private ────────────────────────────────────────────────────────────────

    def _reject(self, event_type: str, reason: str, details: str) -> bool:
        self._blocked_count += 1
        event = SecurityEvent(
            event_type=event_type,
            timestamp=time.time(),
            command_payload=details,
            verdict="DROPPED",
            token_valid=(event_type != "INVALID_TOKEN"),
            details=reason,
        )
        self.event_emitted.emit(event)
        self.command_blocked.emit(reason)
        return False
