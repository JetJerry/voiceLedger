"""
VoiceLedger Authentication Service Layer.

Encapsulates user registration, email normalization, credential verification,
and domain authentication rules with timing attack mitigation.
"""
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from backend.app.models.user import User
from backend.app.core.security import (
    validate_password_input,
    verify_password,
    PasswordValidationError,
)
from backend.app.core.logging import logger

# Precomputed dummy Argon2id hash to mitigate timing attacks when user is not found
DUMMY_ARGON2_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQxNmJ5dGVz$q0U7J182dIu5V/uBwQ4mC717hH1g9B1N8d2M3K4L5P6"
)


class AuthDomainError(Exception):
    """Base exception for authentication domain errors."""
    pass


class EmailAlreadyExistsError(AuthDomainError):
    """Raised when an email is already registered."""
    pass


class InvalidCredentialsError(AuthDomainError):
    """Raised on invalid credentials. Detail message is always generic."""
    pass


class UserInactiveError(AuthDomainError):
    """Raised when an account exists and password matches but account is inactive."""
    pass


class WeakPasswordError(AuthDomainError):
    """Raised when password validation fails."""
    pass


def normalize_email(email: str) -> str:
    """
    Normalize email address consistently across registration and login:
    - Strips surrounding whitespace
    - Lowercases all characters
    - Validates presence of '@' and a domain containing '.'
    """
    if not isinstance(email, str) or not email.strip():
        raise ValueError("Email must be a non-empty string")
    
    clean_email = email.strip().lower()
    parts = clean_email.split("@")
    if len(parts) != 2 or not parts[0] or not parts[1] or "." not in parts[1]:
        raise ValueError("Invalid email format")
    
    return clean_email


class AuthService:
    """
    Core authentication service for canonical VoiceLedger users.
    """

    def normalize_email(self, email: str) -> str:
        return normalize_email(email)

    def register_user(
        self,
        db: Session,
        email: str,
        password: str,
        full_name: Optional[str] = None,
    ) -> User:
        """
        Register a new canonical User.

        Steps:
        1. Normalize email.
        2. Validate password constraints (length, characters).
        3. Pre-check for duplicate email.
        4. Hash password with Argon2id and persist User.
        5. Handle concurrency races transactionally with rollback on IntegrityError.
        """
        try:
            norm_email = self.normalize_email(email)
        except ValueError as exc:
            raise ValueError(f"Invalid email: {exc}") from exc

        try:
            validate_password_input(password)
        except PasswordValidationError as exc:
            raise WeakPasswordError(str(exc)) from exc

        # Pre-check for existing user
        existing_user = db.query(User).filter(User.email == norm_email).first()
        if existing_user:
            raise EmailAlreadyExistsError("Email address is already registered")

        user = User(
            email=norm_email,
            full_name=full_name.strip() if full_name and full_name.strip() else None,
            is_active=True,
            is_superuser=False,
        )
        user.set_password(password)
        db.add(user)

        try:
            db.commit()
            db.refresh(user)
            logger.info("Registered user id=%s email=%s", user.id, user.email)
            return user
        except IntegrityError as exc:
            db.rollback()
            raise EmailAlreadyExistsError("Email address is already registered") from exc
        except Exception:
            db.rollback()
            raise

    def authenticate_user(
        self,
        db: Session,
        email: str,
        password: str,
    ) -> User:
        """
        Authenticate a user by email and password.

        Security protections:
        - Normalizes email.
        - If email format is invalid or user not found, executes dummy verification
          to mitigate timing side-channel attacks.
        - Uses constant-time Argon2id password verification.
        - Generic InvalidCredentialsError for all credential mismatches.
        - Checks account active status.
        """
        try:
            norm_email = self.normalize_email(email)
        except ValueError:
            # Execute dummy verify to equalize execution time
            verify_password(password or "dummy", DUMMY_ARGON2_HASH)
            raise InvalidCredentialsError("Invalid email or password")

        user = db.query(User).filter(User.email == norm_email).first()

        if not user:
            # Timing mitigation: run full Argon2id verification on dummy hash
            verify_password(password or "dummy", DUMMY_ARGON2_HASH)
            raise InvalidCredentialsError("Invalid email or password")

        if not user.verify_password(password):
            raise InvalidCredentialsError("Invalid email or password")

        if not user.is_active:
            raise UserInactiveError("Account is inactive")

        logger.info("Authenticated user id=%s email=%s", user.id, user.email)
        return user


auth_service = AuthService()
