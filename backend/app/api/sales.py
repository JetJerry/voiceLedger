from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.models import Sale, Product
from backend.app.schemas.sale import SaleCreate, SaleResponse, ProductCreate, ProductResponse
from backend.app.services.sales_service import sales_service

router = APIRouter(prefix="/sales", tags=["Sales & Catalog"])


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
def list_catalog_products(db: Session = Depends(get_db)):
    """
    List all menu and catalog products.
    """
    products = db.query(Product).order_by(Product.name).all()
    return products


@router.post("/catalog/products", response_model=ProductResponse)
def add_catalog_product(product_in: ProductCreate, db: Session = Depends(get_db)):
    """
    Add a new product/item to the merchant catalog.
    """
    merchant = sales_service.get_or_create_merchant(db)
    product = Product(
        merchant_id=merchant.id,
        name=product_in.name.strip().lower(),
        price=product_in.price,
        category=product_in.category or "General"
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product
