import json
import os
from pathlib import Path
from sqlalchemy.orm import Session
from backend.app.db.base import Base
from backend.app.models.legacy import (
    LegacyBase,
    LegacyMerchant as Merchant,
    Customer,
    Product,
    Sale,
    SaleItem,
    Payment,
    WebhookEvent,
    RecoveryAction,
)


from sqlalchemy import text


def _migrate_tables(bind_engine):
    """Auto-migrate existing SQLite tables to add missing columns."""
    with bind_engine.connect() as conn:
        try:
            # 1. Check products table
            result_prod = conn.execute(text("PRAGMA table_info(products);")).fetchall()
            existing_prod_cols = {row[1] for row in result_prod}
            if existing_prod_cols:
                if "description" not in existing_prod_cols:
                    conn.execute(text("ALTER TABLE products ADD COLUMN description TEXT;"))
                if "unit" not in existing_prod_cols:
                    conn.execute(text("ALTER TABLE products ADD COLUMN unit VARCHAR(50);"))
                if "attributes" not in existing_prod_cols:
                    conn.execute(text("ALTER TABLE products ADD COLUMN attributes TEXT DEFAULT '{}';"))
                if "is_active" not in existing_prod_cols:
                    conn.execute(text("ALTER TABLE products ADD COLUMN is_active BOOLEAN DEFAULT 1 NOT NULL;"))
                if "updated_at" not in existing_prod_cols:
                    conn.execute(text("ALTER TABLE products ADD COLUMN updated_at DATETIME;"))

            # 2. Check merchants table
            result_merch = conn.execute(text("PRAGMA table_info(merchants);")).fetchall()
            existing_merch_cols = {row[1] for row in result_merch}
            if existing_merch_cols:
                if "business_type" not in existing_merch_cols:
                    conn.execute(text("ALTER TABLE merchants ADD COLUMN business_type VARCHAR(100) DEFAULT 'Kirana & Retail';"))
                if "phone" not in existing_merch_cols:
                    conn.execute(text("ALTER TABLE merchants ADD COLUMN phone VARCHAR(20);"))
                if "username" not in existing_merch_cols:
                    conn.execute(text("ALTER TABLE merchants ADD COLUMN username VARCHAR(100);"))
                if "password" not in existing_merch_cols:
                    conn.execute(text("ALTER TABLE merchants ADD COLUMN password VARCHAR(255) DEFAULT 'shop123';"))
                if "is_active" not in existing_merch_cols:
                    conn.execute(text("ALTER TABLE merchants ADD COLUMN is_active BOOLEAN DEFAULT 1 NOT NULL;"))
                if "is_current_active" not in existing_merch_cols:
                    conn.execute(text("ALTER TABLE merchants ADD COLUMN is_current_active BOOLEAN DEFAULT 0 NOT NULL;"))
                if "updated_at" not in existing_merch_cols:
                    conn.execute(text("ALTER TABLE merchants ADD COLUMN updated_at DATETIME;"))

            # 3. Check webhook_events table
            result_wh = conn.execute(text("PRAGMA table_info(webhook_events);")).fetchall()
            existing_wh_cols = {row[1] for row in result_wh}
            if existing_wh_cols:
                if "status" not in existing_wh_cols:
                    conn.execute(text("ALTER TABLE webhook_events ADD COLUMN status VARCHAR(50) DEFAULT 'RECEIVED';"))
                if "error_message" not in existing_wh_cols:
                    conn.execute(text("ALTER TABLE webhook_events ADD COLUMN error_message TEXT;"))

            conn.commit()
        except Exception as e:
            # Non-sqlite or other DB engine
            pass


def init_db(db: Session = None) -> None:
    close_db = False
    if db is None:
        from backend.app.db.session import SessionLocal
        db = SessionLocal()
        close_db = True

    bind_engine = db.get_bind()
    if "sqlite" in str(bind_engine.url):
        LegacyBase.metadata.create_all(bind=bind_engine)
        _migrate_tables(bind_engine)

    try:
        # Check if primary merchant exists
        merchant_count = db.query(Merchant).count()
        if merchant_count == 0:
            # Seed from default_catalog.json if present
            catalog_path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "default_catalog.json"
            catalog_data = {}
            if catalog_path.exists():
                with open(catalog_path, "r", encoding="utf-8") as f:
                    catalog_data = json.load(f)

            merchant_info = catalog_data.get("merchant", {"name": "Kirana & Cafe Express", "currency": "INR"})
            merchant = Merchant(
                name=merchant_info["name"],
                currency=merchant_info.get("currency", "INR"),
                business_type=merchant_info.get("business_type", "Kirana & Cafe"),
                phone="+919876500001",
                username="kirana",
                password="shop123",
                is_active=True,
                is_current_active=True,
            )
            db.add(merchant)
            db.commit()
            db.refresh(merchant)

            # Seed products for primary merchant
            products_list = catalog_data.get("products", [])
            for p in products_list:
                prod = Product(
                    merchant_id=merchant.id,
                    name=p["name"].strip().lower(),
                    price=float(p["price"]),
                    category=p.get("category", "General"),
                    unit=p.get("unit"),
                    description=p.get("description"),
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

            # Seed 2 additional sample vendors for multi-merchant admin hub
            vendor2 = Merchant(
                name="Sharma Sweet & Bakery",
                business_type="Bakery & Sweets",
                phone="+919876500002",
                username="bakery",
                password="shop123",
                currency="INR",
                is_active=True,
                is_current_active=False,
            )
            db.add(vendor2)
            db.flush()
            db.add_all([
                Product(merchant_id=vendor2.id, name="gulab jamun", price=40.0, category="Sweets", unit="piece"),
                Product(merchant_id=vendor2.id, name="rasgulla", price=35.0, category="Sweets", unit="piece"),
                Product(merchant_id=vendor2.id, name="kaju katli", price=450.0, category="Sweets", unit="500g box"),
                Product(merchant_id=vendor2.id, name="patties", price=30.0, category="Bakery", unit="piece"),
            ])

            vendor3 = Merchant(
                name="National Stationery & Xerox",
                business_type="Stationery & Printing",
                phone="+919876500003",
                username="stationery",
                password="shop123",
                currency="INR",
                is_active=True,
                is_current_active=False,
            )
            db.add(vendor3)
            db.flush()
            db.add_all([
                Product(merchant_id=vendor3.id, name="a4 paper rim", price=280.0, category="Stationery", unit="packet"),
                Product(merchant_id=vendor3.id, name="stapler", price=90.0, category="Stationery", unit="piece"),
                Product(merchant_id=vendor3.id, name="pen drive 64gb", price=499.0, category="Electronics", unit="piece"),
            ])

            db.commit()
            print(f"Database initialized and seeded with multi-vendor sample merchants.")
        else:
            # Backfill any merchants that have missing username or password
            all_merchants = db.query(Merchant).all()
            changed = False
            for m in all_merchants:
                if not m.username:
                    m.username = m.name.lower().replace(" ", "_").replace("&", "and")[:30]
                    changed = True
                if not m.password:
                    m.password = "shop123"
                    changed = True
            if changed:
                db.commit()

            # Ensure at least one merchant is marked as current active if none is
            active = db.query(Merchant).filter(Merchant.is_current_active == True).first()
            if not active:
                first_m = db.query(Merchant).order_by(Merchant.id.asc()).first()
                if first_m:
                    first_m.is_current_active = True
                    db.commit()
    finally:
        if close_db:
            db.close()


if __name__ == "__main__":
    init_db()

