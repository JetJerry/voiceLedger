"""
VoiceLedger Soundbox Device API Router (API v1).

Endpoints:
- POST /api/v1/merchants/{merchant_id}/devices : Provision a new Soundbox (Merchant Owner/Admin)
- GET  /api/v1/merchants/{merchant_id}/devices : List devices for merchant
- POST /api/v1/devices/{device_id}/authenticate : Authenticate device via secret -> returns session token
- POST /api/v1/devices/{device_id}/heartbeat    : Authenticated device heartbeat telemetry
"""
import logging
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.api.deps import require_role
from backend.app.models.merchant_user import MerchantUser
from backend.app.schemas.device import (
    DeviceCreateRequest,
    DeviceRegisterResponse,
    DeviceResponse,
    DeviceAuthRequest,
    DeviceAuthResponse,
    DeviceHeartbeatResponse,
)
from backend.app.services.device_service import (
    device_service,
    DeviceAuthenticationError,
    DeviceInactiveError,
    DeviceSessionInvalidError,
    DeviceNotFoundError,
)

logger = logging.getLogger("voiceledger.api.devices")

router = APIRouter(tags=["Devices"])


# =====================================================================
# 1. Merchant-Authorized Device Management
# =====================================================================

@router.post(
    "/merchants/{merchant_id}/devices",
    response_model=DeviceRegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_device_endpoint(
    merchant_id: uuid.UUID,
    request_data: DeviceCreateRequest,
    membership: MerchantUser = Depends(require_role("OWNER", "ADMIN")),
    db: Session = Depends(get_db),
):
    """
    Register a new physical Soundbox under the merchant organization.
    Returns the one-time device_secret required to provision the hardware.
    Requires merchant OWNER or ADMIN role.
    """
    try:
        device, raw_secret = device_service.register_device(
            db=db,
            merchant_id=membership.merchant_id,
            device_name=request_data.device_name,
            device_type=request_data.device_type or "SOUNDBOX",
        )
        db.commit()
        db.refresh(device)

        return DeviceRegisterResponse(
            id=device.id,
            merchant_id=device.merchant_id,
            device_name=device.device_name,
            device_type=device.device_type,
            status=device.status,
            created_at=device.created_at,
            device_secret=raw_secret,
        )
    except DeviceInactiveError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except Exception as exc:
        db.rollback()
        logger.error("Error registering device: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to register device")


@router.get(
    "/merchants/{merchant_id}/devices",
    response_model=List[DeviceResponse],
    status_code=status.HTTP_200_OK,
)
def list_merchant_devices_endpoint(
    merchant_id: uuid.UUID,
    membership: MerchantUser = Depends(require_role("OWNER", "ADMIN", "STAFF")),
    db: Session = Depends(get_db),
):
    """
    List all devices provisioned for the merchant organization.
    Strictly omits secrets and token hashes.
    """
    devices_with_status = device_service.list_devices(db=db, merchant_id=membership.merchant_id)
    return [
        DeviceResponse(
            id=d.id,
            merchant_id=d.merchant_id,
            device_name=d.device_name,
            device_type=d.device_type,
            status=d.status,
            is_online=is_online,
            last_seen_at=d.last_seen_at,
            created_at=d.created_at,
        )
        for d, is_online in devices_with_status
    ]


# =====================================================================
# 2. Hardware Device Handshake & Telemetry
# =====================================================================

@router.post(
    "/devices/{device_id}/authenticate",
    response_model=DeviceAuthResponse,
    status_code=status.HTTP_200_OK,
)
def authenticate_device_endpoint(
    device_id: uuid.UUID,
    request_data: DeviceAuthRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Physical Soundbox authentication handshake.
    Exchanges provisioned device_secret for an active DeviceSession bearer token.
    """
    ip_addr = request.client.host if request.client else None
    ua = request.headers.get("user-agent")

    try:
        session, raw_session_token = device_service.authenticate_device(
            db=db,
            device_id=device_id,
            raw_secret=request_data.device_secret,
            ip_address=ip_addr,
            user_agent=ua,
        )
        db.commit()

        device = session.device
        return DeviceAuthResponse(
            session_token=raw_session_token,
            device_id=device.id,
            merchant_id=device.merchant_id,
            status=device.status,
            expires_at=session.expires_at,
        )
    except DeviceAuthenticationError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    except DeviceInactiveError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except Exception as exc:
        db.rollback()
        logger.error("Unexpected error during device authentication: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Device authentication failed")


@router.post(
    "/devices/{device_id}/heartbeat",
    response_model=DeviceHeartbeatResponse,
    status_code=status.HTTP_200_OK,
)
def device_heartbeat_endpoint(
    device_id: uuid.UUID,
    x_device_session_token: Optional[str] = Header(None, alias="X-Device-Session-Token"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Periodic heartbeat from Soundbox hardware to update last_seen telemetry.
    Requires active DeviceSession token.
    """
    token = x_device_session_token
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing device session token",
        )

    try:
        device = device_service.record_heartbeat(
            db=db,
            device_id=device_id,
            raw_session_token=token,
        )
        db.commit()
        return DeviceHeartbeatResponse(
            status="ok",
            device_id=device.id,
            device_status=device.status,
            last_seen_at=device.last_seen_at,
        )
    except DeviceSessionInvalidError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    except DeviceInactiveError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except DeviceNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        db.rollback()
        logger.error("Unexpected error during device heartbeat: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Heartbeat failed")
