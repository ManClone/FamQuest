"""OAuth 2.0 PKCE S256 primitives.

This module does not issue tokens or authorize users. The authorization server
must additionally bind one-time codes to client, redirect URI, identity and tenant.
"""

import base64
import hashlib
import hmac
import re

_VERIFIER = re.compile(r"^[A-Za-z0-9._~-]{43,128}$")
_CHALLENGE = re.compile(r"^[A-Za-z0-9_-]{43}$")


def s256_challenge(verifier: str) -> str:
    """Return the unpadded base64url SHA-256 digest of a valid PKCE verifier."""
    if not isinstance(verifier, str) or not _VERIFIER.fullmatch(verifier):
        raise ValueError("Invalid PKCE code verifier")
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def verify_s256(verifier: str, challenge: str, method: str) -> bool:
    """Only accept RFC 7636 S256; never downgrade to plain."""
    if method != "S256" or not isinstance(challenge, str):
        return False
    if not _CHALLENGE.fullmatch(challenge):
        return False
    try:
        expected = s256_challenge(verifier)
    except ValueError:
        return False
    return hmac.compare_digest(expected, challenge)
