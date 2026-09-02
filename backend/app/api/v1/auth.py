"""
VoiceLedger Canonical Authentication Endpoints (API v1).

Implements user registration, login, token refresh with rotation & reuse detection,
logout, and authenticated user identity retrieval.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.schemas.auth import (
    UserRegisterRequest,
    UserRegisterResponse,
    UserLoginRequest,
    UserLoginResponse,
    TokenRefreshRequest,
    TokenRefreshResponse,
    LogoutRequest,
    LogoutResponse,
    UserResponse,
)
from backend.app.services.auth_service import (
    auth_service,
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    UserInactiveError,
    WeakPasswordError,
)
from backend.app.core.security import (
    create_access_token,
    InvalidTokenError,
    TokenExpiredError,
    TokenReuseError,
)
from backend.app.api.deps import get_current_user
from backend.app.core.logging import logger

import ipaddress
from typing import Optional

router = APIRouter(prefix="/auth", tags=["Authentication (v1)"])


def _extract_client_ip(http_request: Request) -> Optional[str]:
    """Safely extract and validate client IP address for PostgreSQL INET storage."""
    if not http_request.client or not http_request.client.host:
        return None
    host = http_request.client.host
    if host == "testclient":
        return "127.0.0.1"
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        return None


@router.post(
    "/register",
    response_model=UserRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Registers a new platform user with Argon2id password hashing.",
)
def register_user(
    request: UserRegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Register a new user account.
    """
    try:
        user = auth_service.register_user(
            db=db,
            email=request.email,
            password=request.password,
            full_name=request.full_name,
        )
        return UserRegisterResponse(
            success=True,
            message="User registered successfully",
            user=UserResponse.model_validate(user),
        )
    except EmailAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except (WeakPasswordError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception:
        logger.exception("Unexpected error during registration")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during registration",
        )


@router.post(
    "/login",
    response_model=UserLoginResponse,
    status_code=status.HTTP_200_OK,
    summary="User login & token issuance",
    description="Authenticates credentials and issues short-lived access token + rotating refresh token.",
)
def login_user(
    request_data: UserLoginRequest,
    http_request: Request,
    db: Session = Depends(get_db),
):
    """
    Authenticate user credentials, create a server-side session, and issue tokens.
    """
    try:
        user = auth_service.authenticate_user(
            db=db,
            email=request_data.email,
            password=request_data.password,
        )
        # Capture client context for session audit
        client_ip = _extract_client_ip(http_request)
        user_agent = http_request.headers.get("user-agent")

        # Create refresh session in PostgreSQL
        session, raw_refresh_token = auth_service.create_user_session(
            db=db,
            user=user,
            ip_address=client_ip,
            user_agent=user_agent,
        )

        # Generate short-lived JWT access token
        access_token = create_access_token(user.id, user.email)
        expires_in = settings.JWT_ACCESS_TTL_MINUTES * 60

        return UserLoginResponse(
            success=True,
            status="authenticated",
            message="Credentials verified successfully",
            access_token=access_token,
            refresh_token=raw_refresh_token,
            token_type="bearer",
            expires_in=expires_in,
            user=UserResponse.model_validate(user),
        )
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    except UserInactiveError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )
    except Exception:
        logger.exception("Unexpected error during login")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during authentication",
        )


@router.post(
    "/refresh",
    response_model=TokenRefreshResponse,
    status_code=status.HTTP_200_OK,
    summary="Rotate refresh token",
    description="Rotates the refresh token and issues a new access token. Replay/reuse revokes the session family.",
)
def refresh_token(
    request_data: TokenRefreshRequest,
    http_request: Request,
    db: Session = Depends(get_db),
):
    """
    Rotate a refresh token and issue a new access token.
    """
    client_ip = _extract_client_ip(http_request)
    user_agent = http_request.headers.get("user-agent")

    try:
        user, new_access_token, new_refresh_token, expires_in = auth_service.rotate_refresh_token(
            db=db,
            raw_refresh_token=request_data.refresh_token,
            ip_address=client_ip,
            user_agent=user_agent,
        )
        return TokenRefreshResponse(
            success=True,
            token_type="bearer",
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            expires_in=expires_in,
        )
    except TokenReuseError:
        logger.warning("Token reuse detected during refresh request")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked refresh token",
        )
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired",
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    except UserInactiveError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )
    except Exception:
        logger.exception("Unexpected error during token refresh")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during token refresh",
        )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke session / logout",
    description="Revokes the presented refresh token session idempotently.",
)
def logout(
    request_data: LogoutRequest,
    db: Session = Depends(get_db),
):
    """
    Revoke a refresh token session.
    """
    try:
        if request_data.refresh_token:
            auth_service.revoke_refresh_token(db, request_data.refresh_token)
        return LogoutResponse(
            success=True,
            message="Logged out successfully",
        )
    except Exception:
        logger.exception("Unexpected error during logout")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during logout",
        )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
    description="Returns the profile of the currently authenticated user via Bearer token.",
)
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
):
    """
    Protected endpoint to test and retrieve current authenticated user.
    """
    return UserResponse.model_validate(current_user)
