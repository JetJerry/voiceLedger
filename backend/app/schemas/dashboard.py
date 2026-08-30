from typing import List
from pydantic import BaseModel
from backend.app.schemas.sale import SaleResponse
from backend.app.schemas.recovery import RecoveryPriorityItem


class DashboardSummary(BaseModel):
    today_sales: float
    total_collected: float
    total_outstanding: float
    total_transactions: int
    paid_count: int
    partial_count: int
    pending_count: int
    failed_count: int
    recovery_priority_items: List[RecoveryPriorityItem] = []
    recent_sales: List[SaleResponse] = []
