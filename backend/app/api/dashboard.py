from typing import Optional
from datetime import datetime, date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.models import Sale, Merchant
from backend.app.schemas.dashboard import DashboardSummary
from backend.app.schemas.sale import SaleResponse
from backend.app.services.recovery_service import recovery_service
from backend.app.services.sales_service import sales_service

router = APIRouter(prefix="/dashboard", tags=["Merchant Dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    merchant_id: Optional[int] = Query(None, description="Optional merchant filter"),
    db: Session = Depends(get_db)
):
    """
    Returns comprehensive metrics for the Merchant Dashboard.
    """
    today_start = datetime.combine(date.today(), datetime.min.time())
    
    # Filter by merchant if specified or get active merchant
    query = db.query(Sale)
    if merchant_id:
        query = query.filter(Sale.merchant_id == merchant_id)
    else:
        active_m = sales_service.get_or_create_merchant(db)
        if active_m:
            query = query.filter(Sale.merchant_id == active_m.id)

    all_sales = query.order_by(Sale.created_at.desc()).all()
    
    # Today's sales
    today_sales_sum = sum(s.total_amount for s in all_sales if s.created_at >= today_start)
    total_collected_sum = sum(s.received_amount for s in all_sales)
    total_outstanding_sum = sum(s.outstanding_amount for s in all_sales)
    
    paid_count = sum(1 for s in all_sales if s.status == "PAID")
    partial_count = sum(1 for s in all_sales if s.status == "PARTIAL")
    pending_count = sum(1 for s in all_sales if s.status == "PENDING")
    failed_count = sum(1 for s in all_sales if s.status == "FAILED")
    
    # Recovery queue
    recovery_items = recovery_service.get_recovery_queue(db)[:5]
    
    recent_sales = [SaleResponse.from_orm(s) for s in all_sales[:15]]

    return DashboardSummary(
        today_sales=round(today_sales_sum, 2),
        total_collected=round(total_collected_sum, 2),
        total_outstanding=round(total_outstanding_sum, 2),
        total_transactions=len(all_sales),
        paid_count=paid_count,
        partial_count=partial_count,
        pending_count=pending_count,
        failed_count=failed_count,
        recovery_priority_items=recovery_items,
        recent_sales=recent_sales
    )
