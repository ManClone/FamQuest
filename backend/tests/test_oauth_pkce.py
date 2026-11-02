"""Tests for RFC 7636 PKCE primitives."""

import pytest

from app.oauth_pkce import s256_challenge, verify_s256


def test_rfc7636_vector():
    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    challenge = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    assert s256_challenge(verifier) == challenge
    assert verify_s256(verifier, challenge, "S256")


@pytest.mark.parametrize("method", ["plain", "", "s256", None])
def test_reject_downgrade(method):
    verifier = "a" * 43
    assert not verify_s256(verifier, s256_challenge(verifier), method)


@pytest.mark.parametrize("verifier", ["short", "x" * 129, "ä" * 43, "a" * 42 + " "])
def test_reject_invalid_verifier(verifier):
    with pytest.raises(ValueError):
        s256_challenge(verifier)
    assert not verify_s256(verifier, "a" * 43, "S256")


def test_reject_wrong_challenge():
    verifier = "a" * 43
    assert not verify_s256(verifier, s256_challenge("b" * 43), "S256")
    assert not verify_s256(verifier, "invalid", "S256")
