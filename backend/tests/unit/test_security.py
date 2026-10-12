"""
Requires passlib[bcrypt] and python-jose — not runnable in an environment
without those installed. Run with: pytest tests/unit/test_security.py
"""
import time

import pytest

from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


def test_password_hash_roundtrip():
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"
    assert verify_password("correct horse battery staple", hashed) is True


def test_wrong_password_fails_verification():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("wrong password", hashed) is False


def test_access_token_roundtrip():
    token = create_access_token(user_id="user-1", role="GOVERNMENT_ADMIN")
    payload = decode_token(token, expected_type="access")
    assert payload["sub"] == "user-1"
    assert payload["role"] == "GOVERNMENT_ADMIN"
    assert payload["type"] == "access"


def test_refresh_token_rejected_as_access_token():
    refresh = create_refresh_token(user_id="user-1")
    with pytest.raises(TokenError):
        decode_token(refresh, expected_type="access")


def test_tampered_token_is_rejected():
    token = create_access_token(user_id="user-1", role="HOME_USER")
    tampered = token[:-2] + ("aa" if token[-2:] != "aa" else "bb")
    with pytest.raises(TokenError):
        decode_token(tampered, expected_type="access")


def test_refresh_token_hash_is_deterministic_and_not_reversible_trivially():
    token = create_refresh_token(user_id="user-1")
    h1 = hash_refresh_token(token)
    h2 = hash_refresh_token(token)
    assert h1 == h2
    assert h1 != token
