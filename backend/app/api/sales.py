from typing import List
from fastapi import APIRouter, Depends, HTTPException
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
    merchant = db.query(Merchant).order_by(Merchant.created_at.desc()).first()
    if not merchant:
        merchant = sales_service.get_or_create_merchant(db)
    return merchant


@router.post("/catalog/merchant", response_model=MerchantResponse)
def create_merchant(merchant_in: MerchantCreate, db: Session = Depends(get_db)):
    """Create a merchant record and catalog context for onboarding."""
    merchant = db.query(Merchant).filter(Merchant.name == merchant_in.name.strip()).first()
    if merchant:
        return merchant

    merchant = Merchant(
        name=merchant_in.name.strip(),
        currency=(merchant_in.currency or "INR").upper()
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


# ── Open Catalog Management ──────────────────────────────────────

@router.get("/catalog/products", response_model=List[ProductResponse])
def list_catalog_products(
    category: str = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
):
    """
    List all catalog items. Shopkeepers can add ANY item — not limited to a fixed menu.
    Optionally filter by category or include inactive items.
    """
    query = db.query(Product)
    if active_only:
        query = query.filter(Product.is_active == True)
    if category:
        query = query.filter(Product.category.ilike(f"%{category}%"))
    return query.order_by(Product.category, Product.name).all()


@router.post("/catalog/products", response_model=ProductResponse)
def add_catalog_product(product_in: ProductCreate, db: Session = Depends(get_db)):
    """
    Add ANY new item to the shopkeeper's catalog.
    No restrictions on item type — works for food, stationery, hardware, clothing, etc.
    """
    merchant = sales_service.get_or_create_merchant(db)

    # Check if item already exists (by name, case-insensitive)
    existing = db.query(Product).filter(
        Product.merchant_id == merchant.id,
        Product.name == product_in.name.strip().lower()
    ).first()
    if existing:
        # Reactivate and update price if it was deactivated
        existing.price = product_in.price
        existing.category = product_in.category or existing.category
        existing.description = product_in.description or existing.description
        existing.unit = product_in.unit or existing.unit
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
        existing = db.query(Product).filter(
            Product.merchant_id == merchant.id,
            Product.name == p.name.strip().lower()
        ).first()
        if existing:
            existing.price = p.price
            existing.category = p.category or existing.category
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
    Update an existing catalog item (price, name, category, etc.).
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    for field, value in update.model_dump(exclude_unset=True).items():
        if field == "name" and value:
            value = value.strip().lower()
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

