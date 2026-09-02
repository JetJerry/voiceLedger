"""
VoiceLedger Canonical Merchant Context, RBAC & Tenant-Scoped Endpoints (API v1).
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.merchant import Merchant
from backend.app.models.merchant_user import MerchantUser
from backend.app.schemas.merchant import (
    MerchantContextResponse,
    ResourceAccessResponse,
)
from backend.app.api.deps import (
    get_current_merchant_membership,
    get_current_merchant,
    require_role,
)
from backend.app.services.tenant_service import tenant_service

router = APIRouter(prefix="/merchants", tags=["Merchant Context & RBAC (v1)"])


@router.get(
    "/context",
    response_model=MerchantContextResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current merchant context & user role",
    description="Resolves active merchant context and user role via X-Merchant-ID or sole membership.",
)
def get_merchant_context(
    membership: MerchantUser = Depends(get_current_merchant_membership),
):
    merchant = membership.merchant
    return MerchantContextResponse(
        id=merchant.id,
        name=merchant.name,
        business_type=merchant.business_type,
        status=merchant.status,
        currency=merchant.currency,
        user_role=membership.role,
        created_at=merchant.created_at,
    )


@router.get(
    "/owner-only",
    status_code=status.HTTP_200_OK,
    summary="OWNER-only operation",
    description="Requires OWNER role within the active merchant organization.",
)
def owner_only_endpoint(
    membership: MerchantUser = Depends(require_role("OWNER")),
):
    return {
        "message": "Authorized for OWNER",
        "role": membership.role,
        "merchant_id": str(membership.merchant_id),
    }


@router.get(
    "/admin-only",
    status_code=status.HTTP_200_OK,
    summary="ADMIN or OWNER operation",
    description="Requires ADMIN or OWNER role within the active merchant organization.",
)
def admin_only_endpoint(
    membership: MerchantUser = Depends(require_role("OWNER", "ADMIN")),
):
    return {
        "message": "Authorized for ADMIN or OWNER",
        "role": membership.role,
        "merchant_id": str(membership.merchant_id),
    }


@router.get(
    "/staff-accessible",
    status_code=status.HTTP_200_OK,
    summary="STAFF, ADMIN, or OWNER operation",
    description="Requires STAFF, ADMIN, or OWNER role within the active merchant organization.",
)
def staff_accessible_endpoint(
    membership: MerchantUser = Depends(require_role("OWNER", "ADMIN", "STAFF")),
):
    return {
        "message": "Authorized for STAFF, ADMIN, or OWNER",
        "role": membership.role,
        "merchant_id": str(membership.merchant_id),
    }


@router.get(
    "/payments/{payment_id}",
    response_model=ResourceAccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Tenant-isolated payment access",
    description="Accesses a payment strictly scoped to the active merchant at query level.",
)
def get_tenant_payment(
    payment_id: uuid.UUID,
    merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    payment = tenant_service.get_payment_for_merchant(
        db=db,
        payment_id=payment_id,
        merchant_id=merchant.id,
    )
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )
    return ResourceAccessResponse(
        authorized=True,
        resource_id=payment.id,
        resource_type="payment",
        merchant_id=payment.merchant_id,
    )


@router.get(
    "/devices/{device_id}",
    response_model=ResourceAccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Tenant-isolated device access",
    description="Accesses a device strictly scoped to the active merchant at query level.",
)
def get_tenant_device(
    device_id: uuid.UUID,
    merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    device = tenant_service.get_device_for_merchant(
        db=db,
        device_id=device_id,
        merchant_id=merchant.id,
    )
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )
    return ResourceAccessResponse(
        authorized=True,
        resource_id=device.id,
        resource_type="device",
        merchant_id=device.merchant_id,
    )


@router.get(
    "/device-sessions/{session_id}",
    response_model=ResourceAccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Tenant-isolated device session access",
    description="Accesses a device session scoped via Device relation to the active merchant.",
)
def get_tenant_device_session(
    session_id: uuid.UUID,
    merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    session = tenant_service.get_device_session_for_merchant(
        db=db,
        session_id=session_id,
        merchant_id=merchant.id,
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device session not found",
        )
    return ResourceAccessResponse(
        authorized=True,
        resource_id=session.id,
        resource_type="device_session",
        merchant_id=merchant.id,
    )
