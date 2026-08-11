"""Unit tests for the shared password policy (validate_password_strength):
length bounds only, no composition rules (NIST 800-63B). The same function
gates signup (UserCreate) and password-reset confirm, so these rules apply
everywhere a password is set. The breached-password check is separate — it
lives in the routes (services/hibp_services.py), tested in
tests/auth_tests/test_password_breach.py."""
import pytest

from models.user.user_schemas import (
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    validate_password_strength,
)


# --- length bounds ---

def test_minimum_length_boundary():
    ok = "b" * MIN_PASSWORD_LENGTH
    assert validate_password_strength(ok) == ok

    with pytest.raises(ValueError, match="at least"):
        validate_password_strength("b" * (MIN_PASSWORD_LENGTH - 1))


def test_maximum_length_boundary():
    ok = "b" * MAX_PASSWORD_LENGTH
    assert validate_password_strength(ok) == ok

    with pytest.raises(ValueError, match="or fewer"):
        validate_password_strength("b" * (MAX_PASSWORD_LENGTH + 1))


def test_long_passphrase_is_valid():
    # NIST-style passphrases must pass — no composition rules to trip on
    passphrase = "correct horse battery staple"
    assert validate_password_strength(passphrase) == passphrase
