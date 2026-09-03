"""
VoiceLedger Device & Session Schemas.

Defines Pydantic request and response models for physical soundbox registration,
device authentication, session lifecycle, and heartbeat telemetry.
"""
from datetime import datetime
from typing import Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.device import DeviceType, DeviceStatus


class DeviceCreateRequest(BaseModel):
    """Payload for registering a new Soundbox or client terminal."""
    device_name: str = Field(..., min_length=2, max_length=255, description="Human-readable device identifier")
    device_type: Optional[str] = Field(default=DeviceType.SOUNDBOX.value, description="Hardware type")

    model_config = ConfigDict(from_attributes=True)


class DeviceRegisterResponse(BaseModel):
    """
    Response returned ONLY ONCE upon initial device provisioning.
    Contains the raw device_secret required for the physical soundbox to authenticate.
    """
    id: uuid.UUID
    merchant_id: uuid.UUID
    device_name: str
    device_type: str
    status: str
    created_at: datetime
    device_secret: str = Field(..., description="High-entropy device provisioning secret. Returned ONCE only.")

    model_config = ConfigDict(from_attributes=True)


class DeviceResponse(BaseModel):
    """Public device representation. Strictly omits secret tokens and hashes."""
    id: uuid.UUID
    merchant_id: uuid.UUID
    device_name: str
    device_type: str
    status: str
    is_online: bool
    last_seen_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeviceAuthRequest(BaseModel):
    """Payload presented by the physical Soundbox during connection authentication."""
    device_secret: str = Field(..., min_length=16, description="Provisioned device authentication secret")

    model_config = ConfigDict(from_attributes=True)


class DeviceAuthResponse(BaseModel):
    """Session credentials issued to an authenticated Soundbox."""
    session_token: str = Field(..., description="Active session bearer token for heartbeat and telemetry")
    device_id: uuid.UUID
    merchant_id: uuid.UUID
    status: str
    expires_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeviceHeartbeatResponse(BaseModel):
    """Telemetry acknowledgement returned to the Soundbox."""
    status: str = "ok"
    device_id: uuid.UUID
    device_status: str
    last_seen_at: datetime

    model_config = ConfigDict(from_attributes=True)
