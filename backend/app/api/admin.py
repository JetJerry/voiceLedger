from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.models.legacy import LegacyMerchant as Merchant, Sale, Product
from backend.app.schemas.admin import (
    AdminPlatformMetrics,
    MerchantSummaryItem,
    MerchantDetailResponse,
    MerchantCreateRequest,
    MerchantUpdateRequest,
)
from backend.app.schemas.sale import ProductResponse, SaleResponse

router = APIRouter(prefix="/admin", tags=["Admin Multi-Merchant Hub"])


@router.get("/metrics", response_model=AdminPlatformMetrics)
def get_platform_metrics(db: Session = Depends(get_db)):
    """
    Returns platform-wide aggregate metrics across all registered merchants.
    """
    all_merchants = db.query(Merchant).all()
    all_sales = db.query(Sale).all()

    total_gmv = sum(s.total_amount for s in all_sales)
    total_collected = sum(s.received_amount for s in all_sales)
    total_outstanding = sum(s.outstanding_amount for s in all_sales)
    total_merchants = len(all_merchants)
    active_merchants = sum(1 for m in all_merchants if m.is_active)
    total_transactions = len(all_sales)

    collection_rate = (total_collected / total_gmv * 100.0) if total_gmv > 0 else 100.0

    return AdminPlatformMetrics(
        total_gmv=round(total_gmv, 2),
        total_collected=round(total_collected, 2),
        total_outstanding=round(total_outstanding, 2),
        total_merchants=total_merchants,
        active_merchants=active_merchants,
        total_transactions=total_transactions,
        collection_rate_percent=round(collection_rate, 1),
    )


@router.get("/merchants", response_model=List[MerchantSummaryItem])
def list_merchants(
    search: Optional[str] = Query(None, description="Search by name or category"),
    active_only: bool = False,
    db: Session = Depends(get_db),
):
    """
    Returns all registered merchants with real-time aggregated sales and product counts.
    """
    query = db.query(Merchant)
    if active_only:
        query = query.filter(Merchant.is_active == True)

    merchants = query.order_by(Merchant.created_at.desc()).all()
    results: List[MerchantSummaryItem] = []

    for m in merchants:
        if search:
            s_lower = search.strip().lower()
            m_name = (m.name or "").lower()
            m_type = (m.business_type or "").lower()
            if s_lower not in m_name and s_lower not in m_type:
                continue

        sales = m.sales or []
        sales_vol = sum(s.total_amount for s in sales)
        collected = sum(s.received_amount for s in sales)
        outstanding = sum(s.outstanding_amount for s in sales)
        prods_count = len([p for p in (m.products or []) if p.is_active])

        results.append(
            MerchantSummaryItem(
                id=m.id,
                name=m.name,
                business_type=m.business_type or "Kirana & Retail",
                phone=m.phone,
                currency=m.currency or "INR",
                is_active=m.is_active,
                is_current_active=bool(m.is_current_active),
                created_at=m.created_at or datetime.now(timezone.utc),
                total_sales_count=len(sales),
                total_sales_volume=round(sales_vol, 2),
                total_collected=round(collected, 2),
                total_outstanding=round(outstanding, 2),
                products_count=prods_count,
            )
        )

    return results


@router.post("/merchants", response_model=MerchantSummaryItem)
def create_merchant(
    request: MerchantCreateRequest,
    db: Session = Depends(get_db)
):
    """
    Onboards a new shopkeeper or vendor to the platform.
    """
    clean_name = request.name.strip()
    existing = db.query(Merchant).filter(Merchant.name == clean_name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"A merchant with name '{clean_name}' already exists.")

    new_merchant = Merchant(
        name=clean_name,
        business_type=request.business_type or "Kirana & Retail",
        phone=request.phone.strip() if request.phone else None,
        currency=(request.currency or "INR").upper(),
        is_active=True,
        is_current_active=False,
    )
    db.add(new_merchant)
    db.commit()
    db.refresh(new_merchant)

    return MerchantSummaryItem(
        id=new_merchant.id,
        name=new_merchant.name,
        business_type=new_merchant.business_type,
        phone=new_merchant.phone,
        currency=new_merchant.currency,
        is_active=new_merchant.is_active,
        is_current_active=new_merchant.is_current_active,
        created_at=new_merchant.created_at,
        total_sales_count=0,
        total_sales_volume=0.0,
        total_collected=0.0,
        total_outstanding=0.0,
        products_count=0,
    )


@router.get("/merchants/{merchant_id}", response_model=MerchantDetailResponse)
def get_merchant_detail(merchant_id: int, db: Session = Depends(get_db)):
    """
    Returns detailed profile for a specific merchant, including recent sales and catalog items.
    """
    merchant = db.query(Merchant).filter(Merchant.id == merchant_id).first()
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")

    sales = db.query(Sale).filter(Sale.merchant_id == merchant.id).order_by(Sale.created_at.desc()).all()
    products = db.query(Product).filter(Product.merchant_id == merchant.id, Product.is_active == True).order_by(Product.name).all()

    sales_vol = sum(s.total_amount for s in sales)
    collected = sum(s.received_amount for s in sales)
    outstanding = sum(s.outstanding_amount for s in sales)

    return MerchantDetailResponse(
        id=merchant.id,
        name=merchant.name,
        business_type=merchant.business_type or "Kirana & Retail",
        phone=merchant.phone,
        currency=merchant.currency or "INR",
        is_active=merchant.is_active,
        is_current_active=bool(merchant.is_current_active),
        created_at=merchant.created_at or datetime.now(timezone.utc),
        total_sales_count=len(sales),
        total_sales_volume=round(sales_vol, 2),
        total_collected=round(collected, 2),
        total_outstanding=round(outstanding, 2),
        products_count=len(products),
        recent_sales=[SaleResponse.model_validate(s) for s in sales[:10]],
        catalog_products=[ProductResponse.model_validate(p) for p in products],
    )


@router.put("/merchants/{merchant_id}", response_model=MerchantSummaryItem)
def update_merchant(
    merchant_id: int,
    update: MerchantUpdateRequest,
    db: Session = Depends(get_db)
):
    """
    Updates merchant profile details, business type, phone, or active status.
    """
    merchant = db.query(Merchant).filter(Merchant.id == merchant_id).first()
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")

    if update.name is not None:
        merchant.name = update.name.strip()
    if update.business_type is not None:
        merchant.business_type = update.business_type.strip()
    if update.phone is not None:
        merchant.phone = update.phone.strip() if update.phone else None
    if update.currency is not None:
        merchant.currency = update.currency.upper()
    if update.is_active is not None:
        merchant.is_active = update.is_active

    db.commit()
    db.refresh(merchant)

    sales = merchant.sales or []
    return MerchantSummaryItem(
        id=merchant.id,
        name=merchant.name,
        business_type=merchant.business_type,
        phone=merchant.phone,
        currency=merchant.currency,
        is_active=merchant.is_active,
        is_current_active=bool(merchant.is_current_active),
        created_at=merchant.created_at,
        total_sales_count=len(sales),
        total_sales_volume=round(sum(s.total_amount for s in sales), 2),
        total_collected=round(sum(s.received_amount for s in sales), 2),
        total_outstanding=round(sum(s.outstanding_amount for s in sales), 2),
        products_count=len([p for p in (merchant.products or []) if p.is_active]),
    )


@router.post("/merchants/{merchant_id}/set-active")
def set_active_merchant(merchant_id: int, db: Session = Depends(get_db)):
    """
    Sets the active merchant context for the Store Terminal / Voice Assistant.
    """
    target = db.query(Merchant).filter(Merchant.id == merchant_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Merchant not found")

    # Set all merchants to not current active
    db.query(Merchant).update({Merchant.is_current_active: False})
    target.is_current_active = True
    db.commit()

    return {
        "status": "success",
        "active_merchant": {
            "id": target.id,
            "name": target.name,
            "business_type": target.business_type,
            "currency": target.currency,
        },
        "message": f"Store terminal context switched to '{target.name}'.",
    }


@router.delete("/merchants/{merchant_id}")
def deactivate_merchant(merchant_id: int, db: Session = Depends(get_db)):
    """
    Deactivates a merchant store on the platform.
    """
    merchant = db.query(Merchant).filter(Merchant.id == merchant_id).first()
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")

    merchant.is_active = False
    db.commit()
    return {"detail": f"Merchant '{merchant.name}' deactivated successfully."}
