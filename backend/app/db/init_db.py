import json
import os
from pathlib import Path
from sqlalchemy.orm import Session
from backend.app.db.base import Base
from backend.app.db.session import engine, SessionLocal
from backend.app.models import Merchant, Customer, Product, Sale, SaleItem, Payment, WebhookEvent, RecoveryAction


def init_db(db: Session = None) -> None:
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
        
    try:
        # Check if merchant exists
        merchant = db.query(Merchant).first()
        if not merchant:
            # Seed from default_catalog.json if present
            catalog_path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "default_catalog.json"
            catalog_data = {}
            if catalog_path.exists():
                with open(catalog_path, "r", encoding="utf-8") as f:
                    catalog_data = json.load(f)
            
            merchant_info = catalog_data.get("merchant", {"name": "Kirana & Cafe Express", "currency": "INR"})
            merchant = Merchant(name=merchant_info["name"], currency=merchant_info.get("currency", "INR"))
            db.add(merchant)
            db.commit()
            db.refresh(merchant)
            
            # Seed products
            products_list = catalog_data.get("products", [])
            for p in products_list:
                prod = Product(
                    merchant_id=merchant.id,
                    name=p["name"].strip().lower(),
                    price=float(p["price"]),
                    category=p.get("category", "General")
                )
                db.add(prod)
                
            # Seed customers
            customers_list = catalog_data.get("customers", [])
            for c in customers_list:
                cust = Customer(
                    merchant_id=merchant.id,
                    name=c["name"].strip(),
                    phone=c.get("phone")
                )
                db.add(cust)
                
            db.commit()
            print(f"Database initialized and seeded for merchant '{merchant.name}' (ID: {merchant.id}).")
    finally:
        if close_db:
            db.close()


if __name__ == "__main__":
    init_db()
