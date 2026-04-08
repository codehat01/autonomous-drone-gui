from dataclasses import dataclass, field


@dataclass
class SecurityEvent:
    event_type: str = ""              # VALID / INVALID_RANGE / REPLAY_ATTACK / SPOOFED
    timestamp: float = 0.0
    command_payload: dict = field(default_factory=dict)
    verdict: str = ""                 # ALLOWED / DROPPED
    token_valid: bool = False
    details: str = ""
