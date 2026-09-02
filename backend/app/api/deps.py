"""
VoiceLedger API Dependencies.

Provides the canonical get_current_user dependency injection for authenticated endpoints.
Supports standard HTTP Authorization Bearer tokens.
"""
from typing import Optional
import uuid
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.core.security import (
    decode_access_token,
    TokenExpiredError,
    InvalidTokenError,
)

# HTTPBearer with auto_error=False allows returning custom 401 JSON responses
security_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency to extract and authenticate the current canonical User
    from the HTTP Bearer Authorization header.

    Verifies:
    1. Authorization header presence and Bearer scheme.
    2. JWT cryptographic signature and expiration.
    3. Token 'type' claim is strictly 'access'.
    4. Valid User UUID in 'sub' claim.
    5. User exists in PostgreSQL.
    6. User account is active (is_active=True).
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        payload = decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_uuid = uuid.UUID(str(user_id_str))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user identifier in token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_uuid).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    return user


# =====================================================================
# Merchant Context & RBAC Authorization Dependencies (Phase 2.4)
# =====================================================================
import enum
from typing import Set, Union
from fastapi import Header
from backend.app.models.merchant import Merchant
from backend.app.models.merchant_user import MerchantUser


class MerchantRole(str, enum.Enum):
    """Canonical VoiceLedger RBAC roles."""
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    STAFF = "STAFF"


def get_current_merchant_membership(
    merchant_id: Optional[uuid.UUID] = None,
    x_merchant_id: Optional[str] = Header(None, alias="X-Merchant-ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MerchantUser:
    """
    Resolve and authorize the merchant context for the authenticated user.

    Enforcement:
    1. Extracts target merchant ID from path parameter or 'X-Merchant-ID' header.
    2. If omitted, falls back to the user's sole merchant membership if unambiguous.
    3. If user belongs to 0 merchants -> 403 Forbidden.
    4. If user belongs to multiple merchants and none specified -> 400 Bad Request.
    5. Verifies membership exists in PostgreSQL -> 403 Forbidden if not a member.
    6. Verifies merchant status is ACTIVE -> 403 Forbidden if deactivated.
    """
    target_merchant_id = merchant_id
    if target_merchant_id is None and x_merchant_id is not None:
        try:
            target_merchant_id = uuid.UUID(x_merchant_id.strip())
        except (ValueError, AttributeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid X-Merchant-ID header format",
            )

    if target_merchant_id is None:
        memberships = (
            db.query(MerchantUser)
            .filter(MerchantUser.user_id == current_user.id)
            .all()
        )
        if len(memberships) == 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not belong to any merchant organization",
            )
        if len(memberships) > 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Multiple merchant memberships found. Please specify X-Merchant-ID header",
            )
        target_merchant_id = memberships[0].merchant_id

    # Query-level tenant verification
    membership = (
        db.query(MerchantUser)
        .join(Merchant, MerchantUser.merchant_id == Merchant.id)
        .filter(
            MerchantUser.user_id == current_user.id,
            MerchantUser.merchant_id == target_merchant_id,
        )
        .first()
    )

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: User is not a member of the requested merchant",
        )

    if membership.merchant.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Merchant organization is not active",
        )

    return membership


def get_current_merchant(
    membership: MerchantUser = Depends(get_current_merchant_membership),
) -> Merchant:
    """
    FastAPI dependency returning the authorized canonical Merchant instance.
    """
    return membership.merchant


class RoleChecker:
    """
    Reusable RBAC role authorization dependency factory.
    Verifies the user's role against explicit allowed-role sets.
    """
    def __init__(self, *allowed_roles: Union[str, MerchantRole]):
        self.allowed_roles: Set[str] = {
            r.value if hasattr(r, "value") else str(r).upper()
            for r in allowed_roles
        }

    def __call__(
        self,
        membership: MerchantUser = Depends(get_current_merchant_membership),
    ) -> MerchantUser:
        user_role = str(membership.role).upper()
        if user_role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Insufficient role permissions. Required: {sorted(list(self.allowed_roles))}",
            )
        return membership


def require_role(*allowed_roles: Union[str, MerchantRole]) -> RoleChecker:
    """
    Dependency factory requiring one of the specified roles:
    - Depends(require_role("OWNER"))
    - Depends(require_role("OWNER", "ADMIN"))
    - Depends(require_role("OWNER", "ADMIN", "STAFF"))
    """
    return RoleChecker(*allowed_roles)
