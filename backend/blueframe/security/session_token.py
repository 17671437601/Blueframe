from __future__ import annotations

import hmac
import secrets


def generate_session_token() -> str:
    return secrets.token_hex(32)


class SessionTokenVerifier:
    def __init__(self, expected: str) -> None:
        if len(expected) != 64:
            raise ValueError("session token must be 256 bits")
        self._expected = expected

    def verify(self, candidate: str | None) -> bool:
        if candidate is None or len(candidate) != 64:
            return False
        return hmac.compare_digest(self._expected, candidate)
