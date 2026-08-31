import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.models import Merchant, Sale, Product
from backend.app.schemas.merchant import MerchantCreate, MerchantResponse
from backend.app.schemas.sale import SaleCreate, SaleResponse, ProductCreate, ProductUpdate, ProductResponse
from backend.app.services.sales_service import sales_service

router = APIRouter(prefix="/sales", tags=["Sales & Catalog"])


@router.get("/catalog/merchant", response_model=MerchantResponse)
def get_merchant(db: Session = Depends(get_db)):
    """Return the currently active merchant profile for the catalog."""
    merchant = sales_service.get_or_create_merchant(db)
    return merchant


@router.post("/catalog/merchant", response_model=MerchantResponse)
def create_merchant(merchant_in: MerchantCreate, db: Session = Depends(get_db)):
    """Create a merchant record and catalog context for onboarding."""
    # Deactivate existing active flags
    db.query(Merchant).update({Merchant.is_current_active: False})

    merchant = db.query(Merchant).filter(Merchant.name == merchant_in.name.strip()).first()
    if merchant:
        merchant.is_current_active = True
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

