import json
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.models import Merchant, Sale, Product, MerchantProfile
from backend.app.schemas.merchant import MerchantCreate, MerchantResponse, MerchantProfileCreate, MerchantProfileResponse
from backend.app.schemas.sale import SaleCreate, SaleResponse, ProductCreate, ProductUpdate, ProductResponse
from backend.app.services.sales_service import sales_service
from backend.app.services.llm_service import llm_service
from fastapi import Body


router = APIRouter(prefix="/sales", tags=["Sales & Catalog"])


@router.get("/catalog/merchant", response_model=MerchantResponse)
def get_merchant(db: Session = Depends(get_db)):
    """Return the currently active merchant profile for the catalog."""
    merchant = sales_service.get_or_create_merchant(db)
    return merchant


@router.post("/catalog/merchant", response_model=MerchantResponse)
def create_merchant(merchant_in: MerchantCreate, db: Session = Depends(get_db)):
    """Create a merchant record and catalog context for onboarding."""
    # Deactivate existing active flags if present
    try:
        db.query(Merchant).update({Merchant.is_current_active: False})
    except Exception:
        pass

    merchant = db.query(Merchant).filter(Merchant.name == merchant_in.name.strip()).first()
    if merchant:
        # Ensure merchant is active/current
        merchant.is_current_active = True
        merchant.is_active = True
        db.commit()
        db.refresh(merchant)
        return merchant

    merchant = Merchant(
        name=merchant_in.name.strip(),
        currency=(merchant_in.currency or "INR").upper(),
        is_active=True,
        is_current_active=True,
    )
    db.add(merchant)
    db.commit()
    db.refresh(merchant)
    return merchant


@router.get("/catalog/merchant/profile", response_model=MerchantProfileResponse)
def get_merchant_profile(db: Session = Depends(get_db)):
    """Get the merchant's dynamic business profile (JSON configuration)."""
    merchant = sales_service.get_or_create_merchant(db)

    profile = db.query(MerchantProfile).filter(MerchantProfile.merchant_id == merchant.id).first()
    if not profile:
        return {
            "id": 0,
            "merchant_id": merchant.id,
            "config": {},
            "created_at": merchant.created_at,
            "updated_at": merchant.created_at,
        }

    try:
        cfg = json.loads(profile.config_json)
    except Exception:
        cfg = {}

    return {
        "id": profile.id,
        "merchant_id": profile.merchant_id,
        "config": cfg,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


@router.post("/catalog/merchant/profile", response_model=MerchantProfileResponse)
def upsert_merchant_profile(profile_in: MerchantProfileCreate, db: Session = Depends(get_db)):
    """Create or update merchant dynamic profile.

    Stores merchant-specific configuration used as context for the AI and frontend.
    """
    merchant = sales_service.get_or_create_merchant(db)
    cfg_text = json.dumps(profile_in.config or {})

    profile = db.query(MerchantProfile).filter(MerchantProfile.merchant_id == merchant.id).first()
    if not profile:
        profile = MerchantProfile(merchant_id=merchant.id, config_json=cfg_text)
        db.add(profile)
    else:
        profile.config_json = cfg_text
        from datetime import datetime, timezone
        profile.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(profile)

    return {
        "id": profile.id,
        "merchant_id": profile.merchant_id,
        "config": profile_in.config,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


@router.post("", response_model=SaleResponse)
def create_sale(sale_in: SaleCreate, db: Session = Depends(get_db)):
    """
    Creates a new sale and automatically creates a Razorpay payment link.
    """
    sale = sales_service.create_sale(db, sale_in)
    return sale


@router.get("", response_model=List[SaleResponse])
def list_sales(limit: int = 50, db: Session = Depends(get_db)):
    """
    List all recent sales.
    """
    sales = db.query(Sale).order_by(Sale.created_at.desc()).limit(limit).all()
    return sales


@router.get("/{sale_id}", response_model=SaleResponse)
def get_sale(sale_id: str, db: Session = Depends(get_db)):
    """
    Get detailed sale information by ID.
    """
    sale = sales_service.get_sale_by_id(db, sale_id)
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    return sale


@router.get("/catalog/products", response_model=List[ProductResponse])
def list_catalog_products(
    merchant_id: Optional[int] = Query(None, description="Filter by merchant ID (defaults to active merchant)"),
    category: Optional[str] = None,
    active_only: bool = True,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    List all catalog items. Supports open/dynamic schema for any store domain.
    """
    query = db.query(Product)
    if merchant_id:
        query = query.filter(Product.merchant_id == merchant_id)
    else:
        active_m = sales_service.get_or_create_merchant(db)
        if active_m:
            query = query.filter(Product.merchant_id == active_m.id)

    if active_only:
        query = query.filter(Product.is_active == True)
    if category and category.upper() != "ALL":
        query = query.filter(Product.category.ilike(f"%{category}%"))
    if search:
        s = f"%{search.strip().lower()}%"
        query = query.filter((Product.name.ilike(s)) | (Product.category.ilike(s)) | (Product.description.ilike(s)))

    products = query.order_by(Product.category, Product.name).all()
    return products


@router.post("/catalog/merchant/profile/preview")
def preview_merchant_profile(profile_in: MerchantProfileCreate = Body(...), db: Session = Depends(get_db)):
    """LLM-driven profile preview / validation.

    Accepts a proposed profile (JSON) and returns a suggested modules list and short summary as produced by the configured LLM provider.
    """
    profile = profile_in.config or {}
    summary = llm_service.provider.summarize_profile(profile)
    # Ensure a stable structure
    return {"preview": summary}


@router.get("/admin/merchant/{merchant_id}/profile/export")
def export_merchant_profile(merchant_id: int, db: Session = Depends(get_db)):
    """Export merchant profile JSON for admin/backup purposes."""
    merchant = db.query(Merchant).filter(Merchant.id == merchant_id).first()
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")
    profile = db.query(MerchantProfile).filter(MerchantProfile.merchant_id == merchant.id).first()
    if not profile:
        return {"merchant_id": merchant.id, "config": {}}
    try:
        cfg = json.loads(profile.config_json)
    except Exception:
        cfg = {}
    return {"merchant_id": merchant.id, "config": cfg}


@router.post("/admin/merchant/{merchant_id}/profile/import")
def import_merchant_profile(merchant_id: int, profile_json: Dict[str, Any] = Body(...), db: Session = Depends(get_db)):
    """Import / upsert merchant profile JSON for admin usage."""
    merchant = db.query(Merchant).filter(Merchant.id == merchant_id).first()
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")
    cfg_text = json.dumps(profile_json or {})
    profile = db.query(MerchantProfile).filter(MerchantProfile.merchant_id == merchant.id).first()
    if not profile:
        profile = MerchantProfile(merchant_id=merchant.id, config_json=cfg_text)
        db.add(profile)
    else:
        profile.config_json = cfg_text
        from datetime import datetime, timezone
        profile.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(profile)
    try:
        parsed = json.loads(profile.config_json)
    except Exception:
        parsed = {}
    return {"merchant_id": merchant.id, "config": parsed}


@router.post("/catalog/products", response_model=ProductResponse)
def add_catalog_product(product_in: ProductCreate, db: Session = Depends(get_db)):
    """
    Add ANY new item to the shopkeeper's catalog with dynamic open schema.
    Works for fruits, vegetables, pharmacy, grocery, cafe, hardware, clothing, etc.
    """
    merchant = sales_service.get_or_create_merchant(db)
    attrs_str = json.dumps(product_in.attributes or {})

    # Check if item already exists (by name, case-insensitive)
    existing = db.query(Product).filter(
        Product.merchant_id == merchant.id,
        Product.name == product_in.name.strip().lower()
    ).first()
    if existing:
        existing.price = product_in.price
        existing.category = product_in.category or existing.category
        existing.description = product_in.description or existing.description
        existing.unit = product_in.unit or existing.unit
        existing.attributes = attrs_str
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return existing

    product = Product(
        merchant_id=merchant.id,
        name=product_in.name.strip().lower(),
        price=product_in.price,
        category=product_in.category or "General",
        description=product_in.description,
        unit=product_in.unit,
        attributes=attrs_str,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.post("/catalog/products/bulk", response_model=List[ProductResponse])
def add_bulk_products(products: List[ProductCreate], db: Session = Depends(get_db)):
    """
    Add multiple items to the catalog at once.
    """
    merchant = sales_service.get_or_create_merchant(db)
    results = []
    for p in products:
        attrs_str = json.dumps(p.attributes or {})
        existing = db.query(Product).filter(
            Product.merchant_id == merchant.id,
            Product.name == p.name.strip().lower()
        ).first()
        if existing:
            existing.price = p.price
            existing.category = p.category or existing.category
            existing.attributes = attrs_str
            existing.is_active = True
            results.append(existing)
        else:
            product = Product(
                merchant_id=merchant.id,
                name=p.name.strip().lower(),
                price=p.price,
                category=p.category or "General",
                description=p.description,
                unit=p.unit,
                attributes=attrs_str,
            )
            db.add(product)
            results.append(product)
    db.commit()
    for r in results:
        db.refresh(r)
    return results


@router.put("/catalog/products/{product_id}", response_model=ProductResponse)
def update_catalog_product(product_id: int, update: ProductUpdate, db: Session = Depends(get_db)):
    """
    Update an existing catalog item (price, name, category, dynamic attributes, etc.).
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    update_dict = update.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        if field == "name" and value:
            value = value.strip().lower()
        elif field == "attributes" and isinstance(value, dict):
            value = json.dumps(value)
        setattr(product, field, value)

    db.commit()
    db.refresh(product)
    return product


@router.delete("/catalog/products/{product_id}")
def delete_catalog_product(product_id: int, db: Session = Depends(get_db)):
    """
    Soft-delete (deactivate) a catalog item. The item stays in DB for sale history.
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    product.is_active = False
    db.commit()
    return {"detail": f"Product '{product.name}' deactivated", "id": product.id}

