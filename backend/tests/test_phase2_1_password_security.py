import logging
import pytest
import argon2
from argon2 import Type

from backend.app.core.security import (
    hash_password,
    verify_password,
    needs_rehash,
    validate_password_input,
    get_password_hasher,
    PasswordValidationError,
    MIN_PASSWORD_LENGTH,
    MAX_PASSWORD_LENGTH,
)
from backend.app.models.user import User


def test_password_can_be_hashed_successfully():
    """1. Verify that a valid password hashes without error."""
    candidate = "SuperSecretPassword123!"
    p_hash = hash_password(candidate)
    assert p_hash is not None
    assert isinstance(p_hash, str)
    assert len(p_hash) > 50


def test_hash_result_is_not_equal_to_plaintext():
    """2. Verify that the output hash is not equal to the plaintext password."""
    candidate = "SuperSecretPassword123!"
    p_hash = hash_password(candidate)
    assert p_hash != candidate
    assert candidate not in p_hash


def test_correct_password_verifies_successfully():
    """3. Verify that the matching password verifies against the generated hash."""
    candidate = "AccuratePassword987#"
    p_hash = hash_password(candidate)
    assert verify_password(candidate, p_hash) is True


def test_incorrect_password_fails_verification():
    """4. Verify that an incorrect password fails verification."""
    candidate = "AccuratePassword987#"
    wrong_candidate = "WrongPassword987#"
    p_hash = hash_password(candidate)
    assert verify_password(wrong_candidate, p_hash) is False


def test_two_hashes_from_same_password_have_unique_salts():
    """5. Verify that two hashes of the same password produce different values due to random salts."""
    candidate = "RepeatablePassword456$"
    hash_one = hash_password(candidate)
    hash_two = hash_password(candidate)
    assert hash_one != hash_two
    # Both must still verify against the candidate
    assert verify_password(candidate, hash_one) is True
    assert verify_password(candidate, hash_two) is True


def test_empty_and_whitespace_password_rejected():
    """6. Verify that empty or whitespace-only passwords are systematically rejected."""
    with pytest.raises(PasswordValidationError) as exc_empty:
        hash_password("")
    assert "empty" in str(exc_empty.value).lower()

    with pytest.raises(PasswordValidationError) as exc_ws:
        hash_password("        ")
    assert "whitespace" in str(exc_ws.value).lower()


def test_malformed_and_invalid_password_hash_handled_safely():
    """7. Verify that malformed, corrupted, or non-Argon2 hashes fail safely without crashing."""
    candidate = "ValidPassword123!"
    # Corrupted / random strings
    assert verify_password(candidate, "not-a-valid-hash") is False
    assert verify_password(candidate, "$argon2id$v=19$corrupted_data") is False
    assert verify_password(candidate, "") is False
    assert verify_password(candidate, None) is False
    assert verify_password(None, "some_hash") is False


def test_password_is_never_written_to_exception_messages_or_logs(caplog):
    """8. Verify that sensitive password values are never exposed in exception text or logs."""
    sensitive_word = "UltraSecretTokenShouldNeverBeLeakedInLogs!"

    with caplog.at_level(logging.DEBUG):
        # Trigger validation failure
        with pytest.raises(PasswordValidationError) as exc_info:
            validate_password_input("short")

        # Confirm password is not in exception message
        assert sensitive_word not in str(exc_info.value)

        # Hash and verify a password
        h = hash_password(sensitive_word)
        verify_password(sensitive_word, h)

    # Confirm sensitive word was never logged anywhere
    for record in caplog.records:
        assert sensitive_word not in record.getMessage()


def test_hash_format_is_compatible_with_argon2id():
    """9. Verify that generated hashes strictly follow the Argon2id standard format."""
    candidate = "ArgonFormatPassword2026!"
    p_hash = hash_password(candidate)

    # Argon2id format: $argon2id$v=<version>$m=<memory>,t=<iterations>,p=<parallelism>$<salt>$<hash>
    assert p_hash.startswith("$argon2id$")
    assert "$v=19$" in p_hash
    assert "$m=" in p_hash
    assert ",t=" in p_hash
    assert ",p=" in p_hash


def test_rehash_detection_works():
    """10. Verify that needs_rehash identifies hashes with outdated parameters."""
    candidate = "RehashCandidatePassword123!"

    # Create hasher with lower iterations (e.g. t=1)
    lower_hasher = argon2.PasswordHasher(time_cost=1, memory_cost=32768, parallelism=1, type=Type.ID)
    old_hash = lower_hasher.hash(candidate)

    # Current settings require t=3, m=65536, p=4
    # old_hash should need rehash
    assert needs_rehash(old_hash) is True

    # A newly created hash with current parameters should NOT need rehash
    fresh_hash = hash_password(candidate)
    assert needs_rehash(fresh_hash) is False

    # Invalid / empty hash should safely return False or True
    assert needs_rehash("") is False
    assert needs_rehash(None) is False
    assert needs_rehash("corrupted_hash") is True


def test_non_string_types_rejected():
    """11. Verify that non-string inputs (None, int, dict, list) are rejected."""
    for invalid_val in [None, 12345678, {"pw": "pass"}, ["pass", "word"], True]:
        with pytest.raises(PasswordValidationError) as exc_info:
            hash_password(invalid_val)
        assert "string" in str(exc_info.value).lower()


def test_password_length_boundary_constraints():
    """12. Verify boundary validation for minimum and maximum password length."""
    # Too short (< 8 chars)
    short_pw = "abc"
    with pytest.raises(PasswordValidationError) as exc_short:
        hash_password(short_pw)
    assert f"at least {MIN_PASSWORD_LENGTH}" in str(exc_short.value)
    assert short_pw not in str(exc_short.value)

    # Exactly minimum length (8 chars) -> should succeed
    exact_min = "12345678"
    assert hash_password(exact_min) is not None

    # Too long (> 128 chars) to mitigate DoS
    long_pw = "A" * (MAX_PASSWORD_LENGTH + 1)
    with pytest.raises(PasswordValidationError) as exc_long:
        hash_password(long_pw)
    assert f"exceed {MAX_PASSWORD_LENGTH}" in str(exc_long.value)
    assert long_pw not in str(exc_long.value)


def test_null_bytes_in_password_rejected():
    """13. Verify passwords containing null bytes are rejected to prevent truncation attacks."""
    with pytest.raises(PasswordValidationError) as exc_null:
        hash_password("Password123\x00extra")
    assert "null byte" in str(exc_null.value).lower()


def test_user_model_password_integration():
    """14. Verify User model set_password and verify_password methods."""
    user = User(
        email="merchant_auth_test@voiceledger.in",
        full_name="Merchant Owner",
        hashed_password="placeholder_initial",
    )

    test_pw = "MerchantSecurePass2026!"
    user.set_password(test_pw)

    # Ensure hashed_password is updated to Argon2id
    assert user.hashed_password.startswith("$argon2id$")
    assert user.hashed_password != test_pw

    # Verify user method
    assert user.verify_password(test_pw) is True
    assert user.verify_password("WrongPassword123!") is False

    # Verify User __repr__ does NOT expose hashed_password or plaintext
    user_repr = repr(user)
    assert test_pw not in user_repr
    assert user.hashed_password not in user_repr
    assert "merchant_auth_test@voiceledger.in" in user_repr
