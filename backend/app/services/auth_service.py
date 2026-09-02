"""
VoiceLedger Authentication Service Layer.

Encapsulates user registration, email normalization, credential verification,
and domain authentication rules with timing attack mitigation.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
import uuid
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from backend.app.config import settings
from backend.app.models.user import User
from backend.app.models.user_session import UserSession
from backend.app.core.security import (
    validate_password_input,
    verify_password,
    PasswordValidationError,
    generate_refresh_token,
    hash_token,
    create_access_token,
    InvalidTokenError,
    TokenExpiredError,
    TokenReuseError,
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

    def create_user_session(
        self,
        db: Session,
        user: User,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[UserSession, str]:
        """
        Create a new server-side refresh token session for an authenticated user.
        Generates an opaque random token, stores its SHA-256 hash in PostgreSQL,
        and returns the session record along with the raw refresh token (returned only once).
        """
        raw_refresh_token = generate_refresh_token()
        token_hash = hash_token(raw_refresh_token)
        family_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=settings.JWT_REFRESH_TTL_DAYS)

        session = UserSession(
            user_id=user.id,
            token_hash=token_hash,
            family_id=family_id,
            parent_id=None,
            is_revoked=False,
            expires_at=expires_at,
            created_at=now,
            last_used_at=now,
            ip_address=ip_address,
            user_agent=user_agent[:500] if user_agent else None,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session, raw_refresh_token

    def rotate_refresh_token(
        self,
        db: Session,
        raw_refresh_token: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[User, str, str, int]:
        """
        Validate and rotate a refresh token session following RFC 6749 BCP:
        1. Look up session by SHA-256 token hash with row lock.
        2. Detect Token Reuse: If the presented token is already revoked,
           immediately revoke all sessions in that family and raise TokenReuseError.
        3. Check expiration.
        4. Invalidate current token (set is_revoked=True).
        5. Issue new child session in the same family with a fresh refresh token.
        6. Issue new short-lived access token.
        """
        try:
            token_hash = hash_token(raw_refresh_token)
        except InvalidTokenError:
            raise InvalidTokenError("Invalid refresh token")

        # Atomic lookup with lock to prevent race conditions during concurrent rotation
        session = (
            db.query(UserSession)
            .filter(UserSession.token_hash == token_hash)
            .with_for_update()
            .first()
        )

        if not session:
            raise InvalidTokenError("Invalid refresh token")

        now = datetime.now(timezone.utc)

        # REUSE DETECTION: If token was already revoked, revoke the entire token family
        if session.is_revoked:
            logger.warning(
                "Security Alert: Refresh token reuse detected for session_id=%s, family_id=%s, user_id=%s",
                session.id,
                session.family_id,
                session.user_id,
            )
            self.revoke_session_family(db, session.family_id)
            raise TokenReuseError("Refresh token has been revoked due to reuse")

        # EXPIRATION CHECK
        if session.expires_at < now:
            session.is_revoked = True
            session.revoked_at = now
            db.commit()
            raise TokenExpiredError("Refresh token has expired")

        # USER STATUS CHECK
        user = db.query(User).filter(User.id == session.user_id).first()
        if not user or not user.is_active:
            session.is_revoked = True
            session.revoked_at = now
            db.commit()
            raise UserInactiveError("Account is inactive")

        # ROTATE: Invalidate current token
        session.is_revoked = True
        session.revoked_at = now
        session.last_used_at = now

        # Create new rotating token in the same family
        new_raw_refresh = generate_refresh_token()
        new_token_hash = hash_token(new_raw_refresh)
        new_expires_at = now + timedelta(days=settings.JWT_REFRESH_TTL_DAYS)

        new_session = UserSession(
            user_id=user.id,
            token_hash=new_token_hash,
            family_id=session.family_id,
            parent_id=session.id,
            is_revoked=False,
            expires_at=new_expires_at,
            created_at=now,
            last_used_at=now,
            ip_address=ip_address,
            user_agent=user_agent[:500] if user_agent else None,
        )
        db.add(new_session)
        db.commit()
        db.refresh(new_session)

        # Issue new short-lived access token
        new_access_token = create_access_token(user.id, user.email)
        expires_in = settings.JWT_ACCESS_TTL_MINUTES * 60

        return user, new_access_token, new_raw_refresh, expires_in

    def revoke_refresh_token(self, db: Session, raw_refresh_token: str) -> bool:
        """
        Revoke a specific refresh token session (e.g. on logout).
        Idempotent operation.
        """
        if not raw_refresh_token or not isinstance(raw_refresh_token, str):
            return True

        try:
            token_hash = hash_token(raw_refresh_token)
        except InvalidTokenError:
            return True

        session = (
            db.query(UserSession)
            .filter(UserSession.token_hash == token_hash)
            .first()
        )
        if session and not session.is_revoked:
            session.is_revoked = True
            session.revoked_at = datetime.now(timezone.utc)
            db.commit()

        return True

    def revoke_session_family(self, db: Session, family_id: uuid.UUID) -> int:
        """
        Revoke all active sessions belonging to a specific token family.
        Triggered when token reuse is detected to contain potential compromise.
        """
        now = datetime.now(timezone.utc)
        count = (
            db.query(UserSession)
            .filter(
                UserSession.family_id == family_id,
                UserSession.is_revoked == False,
            )
            .update({"is_revoked": True, "revoked_at": now})
        )
        db.commit()
        return count


auth_service = AuthService()
