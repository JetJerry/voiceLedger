from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from backend.app.schemas.sale import ProductResponse, SaleResponse


class AdminPlatformMetrics(BaseModel):
    total_gmv: float = Field(default=0.0, description="Total platform sales volume across all merchants")
    total_collected: float = Field(default=0.0, description="Total amount collected across all merchants")
    total_outstanding: float = Field(default=0.0, description="Total outstanding balance across all merchants")
    total_merchants: int = Field(default=0, description="Total registered shopkeepers/vendors")
    active_merchants: int = Field(default=0, description="Total active shopkeepers/vendors")
    total_transactions: int = Field(default=0, description="Total sales transactions across platform")
    collection_rate_percent: float = Field(default=0.0, description="Percentage of GMV successfully collected")


class MerchantSummaryItem(BaseModel):
    id: int
    name: str
    business_type: Optional[str] = "Kirana & Retail"
    phone: Optional[str] = None
    currency: str = "INR"
    is_active: bool = True
    is_current_active: bool = False
    created_at: datetime
    total_sales_count: int = 0
    total_sales_volume: float = 0.0
    total_collected: float = 0.0
    total_outstanding: float = 0.0
    products_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class MerchantDetailResponse(MerchantSummaryItem):
    recent_sales: List[SaleResponse] = []
    catalog_products: List[ProductResponse] = []

    model_config = ConfigDict(from_attributes=True)


class MerchantCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, description="Shop/Vendor Name")
    business_type: Optional[str] = Field(default="Kirana & Retail", description="e.g. Cafe, Grocery, Stationery, Apparel")
    phone: Optional[str] = Field(default=None, description="Contact phone number")
    currency: Optional[str] = Field(default="INR", description="Store currency")


class MerchantUpdateRequest(BaseModel):
    name: Optional[str] = None
    business_type: Optional[str] = None
    phone: Optional[str] = None
    currency: Optional[str] = None
    is_active: Optional[bool] = None
