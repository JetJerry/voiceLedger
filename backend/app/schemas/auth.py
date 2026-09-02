from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., description="Username or email / store handle")
    password: str = Field(..., description="Password")
    role: Optional[str] = Field("merchant", description="'admin' or 'merchant'")


class RegisterMerchantRequest(BaseModel):
    name: str = Field(..., description="Store or Business Name")
    username: str = Field(..., description="Unique login username")
    password: str = Field(..., min_length=4, description="Store login password")
    business_type: Optional[str] = Field("General Retail", description="e.g. Pharmacy, Fruits & Veg, Bakery, Cafe")
    phone: Optional[str] = None
    currency: Optional[str] = "INR"


class UserProfileResponse(BaseModel):
    id: Optional[int] = None
    name: str
    username: str
    role: str  # 'admin' | 'merchant'
    business_type: Optional[str] = None
    phone: Optional[str] = None
    currency: Optional[str] = "INR"
    is_active: bool = True


class LoginResponse(BaseModel):
    success: bool = True
    token: str
    role: str  # 'admin' | 'merchant'
    user: UserProfileResponse
    message: str = "Login successful"


# =====================================================================
# Canonical VoiceLedger Authentication Schemas (Phase 2)
# =====================================================================
import uuid
from datetime import datetime
from pydantic import ConfigDict, EmailStr


class UserRegisterRequest(BaseModel):
    email: EmailStr = Field(..., description="Valid email address for the user")
    password: str = Field(..., min_length=8, max_length=128, description="User password (8-128 characters)")
    full_name: Optional[str] = Field(None, max_length=255, description="Full name of the user")


class UserLoginRequest(BaseModel):
    email: str = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: Optional[str] = None
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserRegisterResponse(BaseModel):
    success: bool = True
    message: str = "User registered successfully"
    user: UserResponse


class UserLoginResponse(BaseModel):
    success: bool = True
    status: str = "authenticated"
    message: str = "Credentials verified successfully"
    user: UserResponse
