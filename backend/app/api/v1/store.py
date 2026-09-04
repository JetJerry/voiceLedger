"""
VoiceLedger Store & Catalog API (v1).

Authoritative merchant endpoints for Product Catalog, Inventory Adjustments,
Sales Order Ledger, Business Presets, and Excel Report Exports.
Strictly enforced under tenant isolation and RBAC.
"""
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Body, Response, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.api.deps import get_current_merchant, require_role, MerchantRole
from backend.app.models.merchant import Merchant
from backend.app.schemas.sale import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    SaleCreate,
    SaleResponse,
    InventoryAdjustRequest,
    InventoryAdjustResponse,
)
from backend.app.services.store_service import store_service
from backend.app.services.analytics_service import analytics_service
from backend.app.services.business_presets import list_business_types, BUSINESS_TYPES

router = APIRouter(prefix="/store", tags=["Store & Catalog v1"])


# ── Products Endpoints ────────────────────────────────────────────────

@router.get("/products", response_model=List[ProductResponse])
def list_products(
    category: Optional[str] = None,
    search: Optional[str] = None,
    active_only: bool = True,
    current_merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    """List catalog products for the authenticated merchant organization."""
    return store_service.list_products(
        db=db,
        merchant_id=current_merchant.id,
        category=category,
        search=search,
        active_only=active_only,
    )


@router.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    product_in: ProductCreate,
    current_merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    """Add or update a product in the merchant store catalog."""
    return store_service.create_product(
        db=db,
        merchant_id=current_merchant.id,
        product_in=product_in,
    )


@router.post("/products/bulk", response_model=List[ProductResponse], status_code=status.HTTP_201_CREATED)
def bulk_create_products(
    products: List[ProductCreate],
    current_merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    """Bulk add multiple products to the catalog."""
    return store_service.bulk_create_products(
        db=db,
        merchant_id=current_merchant.id,
        products=products,
    )


@router.get("/products/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: uuid.UUID,
    current_merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    """Retrieve a single product with tenant isolation."""
    prod = store_service.get_product(db, current_merchant.id, product_id)
    if not prod:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return prod


@router.put("/products/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: uuid.UUID,
    update: ProductUpdate,
    current_merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    """Update an existing product item in the catalog."""
    prod = store_service.update_product(db, current_merchant.id, product_id, update)
    if not prod:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return prod


@router.delete("/products/{product_id}")
def delete_product(
    product_id: uuid.UUID,
    current_merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    """Soft-deactivate a product from active catalog."""
    success = store_service.delete_product(db, current_merchant.id, product_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return {"detail": "Product deactivated", "id": str(product_id)}


# ── Inventory Endpoints ───────────────────────────────────────────────

@router.post("/inventory/adjust", response_model=InventoryAdjustResponse)
def adjust_inventory(
    req: InventoryAdjustRequest,
    current_merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    """Adjust inventory stock quantity for a product."""
    result = store_service.adjust_stock(
        db=db,
        merchant_id=current_merchant.id,
        product_id=req.product_id,
        delta=req.delta,
        reason=req.reason,
    )
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return result


# ── Sales & Orders Endpoints ──────────────────────────────────────────

@router.get("/sales", response_model=List[SaleResponse])
def list_sales(
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = None,
    current_merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    """List recent sales orders for the authenticated merchant."""
    return store_service.list_sales(
        db=db,
        merchant_id=current_merchant.id,
        limit=limit,
        status=status,
    )


@router.post("/sales", response_model=SaleResponse, status_code=status.HTTP_201_CREATED)
def create_sale(
    sale_in: SaleCreate,
    current_merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    """Create a new sale order and generate Razorpay payment link."""
    return store_service.create_sale(
        db=db,
        merchant_id=current_merchant.id,
        sale_in=sale_in,
    )


@router.get("/sales/{sale_id}", response_model=SaleResponse)
def get_sale(
    sale_id: str,
    current_merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    """Get single sale order details."""
    sale = store_service.get_sale(db, current_merchant.id, sale_id)
    if not sale:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sale not found")
    return sale


# ── Business Presets & Profiles ──────────────────────────────────────

@router.get("/business-types")
def get_business_types():
    """List business preset suggestions."""
    return {
        "types": list_business_types(),
        "presets": BUSINESS_TYPES,
    }


@router.post("/business-type")
def set_business_type(
    business_type: str = Body(..., embed=True),
    seed_sample_items: bool = Body(False, embed=True),
    current_merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    """Set merchant business type and optionally seed starter catalog items."""
    return store_service.set_business_type(
        db=db,
        merchant_id=current_merchant.id,
        business_type=business_type,
        seed_sample_items=seed_sample_items,
    )


@router.get("/profile")
def get_store_profile(
    current_merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    """Fetch merchant dynamic profile configuration."""
    return store_service.get_merchant_profile(db, current_merchant.id)


@router.post("/profile")
def update_store_profile(
    config: Dict[str, Any] = Body(...),
    current_merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    """Update merchant dynamic profile configuration."""
    return store_service.upsert_merchant_profile(db, current_merchant.id, config)


# ── Sales Analytics & Excel Export ───────────────────────────────────

@router.get("/analytics/summary")
def get_sales_analytics(
    current_merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    """Get period sales analytics (Today, Week, Month, All-Time)."""
    return analytics_service.get_period_sales_analytics(db, current_merchant.id)


@router.get("/analytics/export/excel")
def export_excel_report(
    current_merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    """Download professionally styled multi-sheet Excel (.xlsx) report."""
    excel_bytes = analytics_service.generate_excel_report(db, current_merchant.id)
    clean_name = current_merchant.name.replace(" ", "_").replace("&", "and")
    date_str = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"VoiceLedger_Report_{clean_name}_{date_str}.xlsx"

    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
