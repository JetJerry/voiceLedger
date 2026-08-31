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
