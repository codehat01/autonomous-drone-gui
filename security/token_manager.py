"""
TokenManager — HMAC-SHA256 command authentication.

Usage:
    tm = TokenManager(secret=b"my-secret-key")
    token = tm.generate(payload_bytes)
    ok = tm.verify(payload_bytes, token)
"""
import hmac
import hashlib
import os


class TokenManager:
    """Generates and verifies HMAC-SHA256 tokens for command authentication."""

    DIGEST_SIZE = 32  # SHA-256 → 32 bytes hex = 64 chars

    def __init__(self, secret: bytes | None = None):
        # Allow override from env for deployment; fall back to provided or random
        env_secret = os.environ.get("DRONE_HMAC_SECRET", "").encode()
        self._secret = env_secret if env_secret else (secret or os.urandom(32))

    def generate(self, payload: bytes) -> str:
        """Return hex-encoded HMAC-SHA256 of payload."""
        return hmac.new(self._secret, payload, hashlib.sha256).hexdigest()

    def verify(self, payload: bytes, token: str) -> bool:
        """Constant-time comparison to prevent timing attacks."""
        expected = self.generate(payload)
        return hmac.compare_digest(expected, token)
