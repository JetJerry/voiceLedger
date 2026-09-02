"""
VoiceLedger Canonical Authentication Endpoints (API v1).

Implements user registration and credential verification.
Tokens (JWT / sessions) are strictly deferred to Phase 2.3.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.auth import (
    UserRegisterRequest,
    UserRegisterResponse,
    UserLoginRequest,
    UserLoginResponse,
    UserResponse,
)
from backend.app.services.auth_service import (
    auth_service,
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    UserInactiveError,
    WeakPasswordError,
)
from backend.app.core.logging import logger

router = APIRouter(prefix="/auth", tags=["Authentication (v1)"])


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
    summary="Verify user login credentials",
    description="Verifies user email and password credentials. Does NOT issue tokens in Phase 2.2.",
)
def login_user(
    request: UserLoginRequest,
    db: Session = Depends(get_db),
):
    """
    Authenticate user credentials.
    """
    try:
        user = auth_service.authenticate_user(
            db=db,
            email=request.email,
            password=request.password,
        )
        return UserLoginResponse(
            success=True,
            status="authenticated",
            message="Credentials verified successfully",
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
