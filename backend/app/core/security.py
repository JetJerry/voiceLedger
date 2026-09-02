"""
VoiceLedger Security Core — Password Hashing & Cryptographic Utilities.

Implements Argon2id password hashing following OWASP and RFC 9106 standards.
All password operations are one-way, use unique automated 16-byte random salts,
and employ constant-time comparison.
"""
from typing import Optional, Union, Dict, Any
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
import jwt
import argon2
from argon2 import Type
from argon2.exceptions import (
    InvalidHashError,
    VerifyMismatchError,
    VerificationError,
)

from backend.app.config import settings

# Password boundary constraints
MIN_PASSWORD_LENGTH: int = 8
MAX_PASSWORD_LENGTH: int = 128


class PasswordValidationError(ValueError):
    """
    Raised when password input fails validation rules.
    Messages MUST NEVER contain user-supplied passwords.
    """
    pass


def validate_password_input(password: str) -> None:
    """
    Validate candidate password input before hashing.

    Security Rules:
    - Must be a string.
    - Cannot be empty or whitespace-only.
    - Must not contain null bytes.
    - Must satisfy minimum length (8 chars) to enforce basic entropy.
    - Must satisfy maximum length (128 chars) to prevent DoS via computational exhaustion.
    - NEVER includes password values in raised exceptions or logs.
    """
    if not isinstance(password, str):
        raise PasswordValidationError("Password must be a valid string")
    if not password:
        raise PasswordValidationError("Password must not be empty")
    if len(password.strip()) == 0:
        raise PasswordValidationError("Password must not be whitespace only")
    if "\x00" in password:
        raise PasswordValidationError("Password must not contain null bytes")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordValidationError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters long"
        )
    if len(password) > MAX_PASSWORD_LENGTH:
        raise PasswordValidationError(
            f"Password must not exceed {MAX_PASSWORD_LENGTH} characters"
        )


def get_password_hasher(
    time_cost: Optional[int] = None,
    memory_cost: Optional[int] = None,
    parallelism: Optional[int] = None,
) -> argon2.PasswordHasher:
    """
    Create and return an Argon2id PasswordHasher configured with VoiceLedger settings.

    Uses Type.ID (Argon2id) with automated, cryptographically secure 16-byte random salts
    and a 32-byte hash length.
    """
    return argon2.PasswordHasher(
        time_cost=time_cost or settings.ARGON2_TIME_COST,
        memory_cost=memory_cost or settings.ARGON2_MEMORY_COST_KIB,
        parallelism=parallelism or settings.ARGON2_PARALLELISM,
        hash_len=32,
        salt_len=16,
        type=Type.ID,
    )


def hash_password(password: str, hasher: Optional[argon2.PasswordHasher] = None) -> str:
    """
    Securely hash a plaintext password using Argon2id.

    Args:
        password: The plaintext candidate password.
        hasher: Optional custom PasswordHasher instance.

    Returns:
        The encoded Argon2id hash string (e.g. '$argon2id$v=19$m=65536,t=3,p=4$...').

    Raises:
        PasswordValidationError: If the input fails validation.
    """
    validate_password_input(password)
    active_hasher = hasher or get_password_hasher()
    return active_hasher.hash(password)


def verify_password(
    password: str,
    password_hash: str,
    hasher: Optional[argon2.PasswordHasher] = None,
) -> bool:
    """
    Verify a candidate password against an encoded password hash in constant time.

    Safely handles malformed, corrupted, or non-matching hashes without raising
    exceptions or leaking sensitive internal diagnostics.

    Args:
        password: The plaintext candidate password.
        password_hash: The stored Argon2 hash string.
        hasher: Optional custom PasswordHasher instance.

    Returns:
        True if the password matches the hash, False otherwise.
    """
    if not isinstance(password, str) or not isinstance(password_hash, str):
        return False
    if not password or not password_hash:
        return False

    active_hasher = hasher or get_password_hasher()
    try:
        return active_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError, VerificationError):
        return False
    except Exception:
        # Prevent any unexpected internal parsing exception from bubbling up
        return False


def needs_rehash(
    password_hash: str,
    hasher: Optional[argon2.PasswordHasher] = None,
) -> bool:
    """
    Determine whether a stored password hash should be recomputed because the
    configured Argon2 parameters (cost, memory, parallelism) have evolved.

    Args:
        password_hash: The stored Argon2 hash string.
        hasher: Optional custom PasswordHasher instance.

    Returns:
        True if the hash was created with different parameters or is outdated;
        False otherwise.
    """
    if not isinstance(password_hash, str) or not password_hash:
        return False

    active_hasher = hasher or get_password_hasher()
    try:
        return active_hasher.check_needs_rehash(password_hash)
    except (InvalidHashError, VerificationError):
        return True
    except Exception:
        return False


# =====================================================================
# Token & Session Security Utilities (Phase 2.3)
# =====================================================================

class TokenError(Exception):
    """Base exception for token errors."""
    pass


class TokenExpiredError(TokenError):
    """Raised when an access or refresh token has expired."""
    pass


class InvalidTokenError(TokenError):
    """Raised when a token signature, type, or claims structure is invalid."""
    pass


class TokenReuseError(TokenError):
    """Raised when an already-revoked refresh token is reused."""
    pass


def generate_refresh_token() -> str:
    """
    Generate an opaque, cryptographically secure 256-bit random refresh token.
    Uses secrets.token_urlsafe to ensure high entropy without plaintext patterns.
    """
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """
    Compute the SHA-256 hex digest of an opaque token for secure server-side storage.
    Ensures plaintext refresh tokens are never persisted in the database.
    """
    if not isinstance(token, str) or not token:
        raise InvalidTokenError("Cannot hash empty or non-string token")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(
    user_id: Union[uuid.UUID, str],
    email: Optional[str] = None,
    expires_delta: Optional[timedelta] = None,
    additional_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Create a signed short-lived JWT access token.

    Contains standard claims:
    - 'sub': User UUID as string
    - 'type': 'access'
    - 'jti': Unique token identifier UUID
    - 'iat': Issued-at timestamp (UTC)
    - 'exp': Expiration timestamp (UTC, default 15 minutes)
    """
    now = datetime.now(timezone.utc)
    expires_in = expires_delta or timedelta(minutes=settings.JWT_ACCESS_TTL_MINUTES)
    expire = now + expires_in

    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if email:
        payload["email"] = email
    if additional_claims:
        payload.update(additional_claims)

    return jwt.encode(
        payload,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decode and verify a JWT access token.

    Validates:
    - Cryptographic signature using configured algorithm (HS256) and secret.
    - Expiration ('exp') timestamp.
    - Token type claim strictly equals 'access' (prevents token-type confusion).
    - Presence of required claims ('sub', 'type', 'exp', 'iat').
    """
    if not token or not isinstance(token, str):
        raise InvalidTokenError("Invalid token")

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["sub", "exp", "iat", "type"]},
        )
        if payload.get("type") != "access":
            raise InvalidTokenError("Invalid token type")
        return payload
    except InvalidTokenError:
        raise
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError("Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise InvalidTokenError("Invalid token") from exc
    except Exception as exc:
        raise InvalidTokenError("Token verification failed") from exc
