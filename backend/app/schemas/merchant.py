from datetime import datetime
from typing import Optional, Any, Dict
import uuid
from pydantic import BaseModel, ConfigDict


# =====================================================================
# Legacy Prototype Schemas (Preserved for compatibility)
# =====================================================================

class MerchantCreate(BaseModel):
    name: str
    business_type: Optional[str] = None
    currency: Optional[str] = "INR"


class MerchantResponse(BaseModel):
    id: int
    name: str
    business_type: Optional[str] = None
    currency: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MerchantProfileCreate(BaseModel):
    config: Dict[str, Any]


class MerchantProfileResponse(BaseModel):
    id: int
    merchant_id: int
    config: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# =====================================================================
# Canonical VoiceLedger Merchant Schemas (Phase 2.4)
# =====================================================================

class MerchantContextResponse(BaseModel):
    """
    Response model for the active merchant context and user role.
    """
    id: uuid.UUID
    name: str
    business_type: Optional[str] = None
    status: str
    currency: str
    user_role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResourceAccessResponse(BaseModel):
    """Generic response confirming authorized access to a tenant-scoped resource."""
    authorized: bool = True
    resource_id: uuid.UUID
    resource_type: str
    merchant_id: uuid.UUID
