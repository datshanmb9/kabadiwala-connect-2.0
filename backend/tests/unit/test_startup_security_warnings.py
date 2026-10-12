"""
Phase 11 security fix: app/main.py logs a loud, non-blocking warning at
startup when the known, publicly-visible-in-source insecure defaults
(JWT_SECRET, ADMIN_DEFAULT_PASSWORD) are still active — deliberately not
a hard failure, since failing startup would break the local demo this
whole project is built around. These tests exercise the actual
function, not just read the source.
"""
import logging

from app.core.config import settings
from app.main import _warn_if_insecure_defaults_active


def test_warns_when_both_defaults_are_still_active(monkeypatch, caplog):
    monkeypatch.setattr(settings, "jwt_secret", "dev-only-secret-override-in-real-env")
    monkeypatch.setattr(settings, "admin_default_password", "admin1234")

    with caplog.at_level(logging.WARNING, logger="kabadiwala.startup"):
        _warn_if_insecure_defaults_active()

    assert len(caplog.records) == 1
    assert "JWT_SECRET" in caplog.text
    assert "ADMIN_DEFAULT_PASSWORD" in caplog.text


def test_warns_for_only_the_specific_default_still_active(monkeypatch, caplog):
    monkeypatch.setattr(settings, "jwt_secret", "a-real-overridden-secret")
    monkeypatch.setattr(settings, "admin_default_password", "admin1234")

    with caplog.at_level(logging.WARNING, logger="kabadiwala.startup"):
        _warn_if_insecure_defaults_active()

    assert "ADMIN_DEFAULT_PASSWORD" in caplog.text
    assert "JWT_SECRET" not in caplog.text


def test_no_warning_when_both_defaults_are_overridden(monkeypatch, caplog):
    monkeypatch.setattr(settings, "jwt_secret", "a-real-overridden-secret")
    monkeypatch.setattr(settings, "admin_default_password", "a-real-overridden-password")

    with caplog.at_level(logging.WARNING, logger="kabadiwala.startup"):
        _warn_if_insecure_defaults_active()

    assert len(caplog.records) == 0


def test_startup_does_not_raise_or_block_app_creation_even_with_insecure_defaults(monkeypatch):
    """The whole point of this being a WARNING and not a hard failure —
    proven by actually calling it, not just by reading the code."""
    monkeypatch.setattr(settings, "jwt_secret", "dev-only-secret-override-in-real-env")
    monkeypatch.setattr(settings, "admin_default_password", "admin1234")
    _warn_if_insecure_defaults_active()  # must not raise
