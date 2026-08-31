import uuid
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from backend.app.config import settings
from backend.app.models import Merchant, Product, Sale, SaleItem
from backend.app.schemas.sale import SaleCreate
from backend.app.services.razorpay_service import razorpay_service


class SalesService:
    def get_or_create_merchant(self, db: Session, merchant_name: Optional[str] = None, currency: str = "INR") -> Merchant:
        if merchant_name:
            merchant = db.query(Merchant).filter(Merchant.name == merchant_name.strip()).first()
            if merchant:
                return merchant

        # 1. Prioritize currently active merchant in terminal
        active_merchant = db.query(Merchant).filter(Merchant.is_current_active == True).first()
        if active_merchant:
            return active_merchant

        # 2. Check by configured default name
        normalized_name = (settings.DEFAULT_MERCHANT_NAME or "VoiceLedger Merchant").strip()
        merchant = db.query(Merchant).filter(Merchant.name == normalized_name).first()
        if merchant:
            return merchant

        # 3. Fallback to latest active merchant
        merchant = db.query(Merchant).filter(Merchant.is_active == True).order_by(Merchant.created_at.desc()).first()
        if merchant:
            return merchant

        merchant = Merchant(name=normalized_name, currency=currency or "INR", is_active=True, is_current_active=True)
        db.add(merchant)
        db.commit()
        db.refresh(merchant)
        return merchant

    def find_product_price(self, db: Session, merchant_id: int, item_name: str) -> Tuple[Optional[Product], Optional[float]]:
        """
        Dynamically matches item name to products table in the database.
        Returns (product, price) or (None, None) if no match — no invented default prices.
        """
        name_lower = item_name.strip().lower()
        
        # 1. Exact match in DB
        product = db.query(Product).filter(
            Product.merchant_id == merchant_id,
            Product.name == name_lower,
            Product.is_active == True,
        ).first()
        if product:
            return product, float(product.price)
            
        # 2. Substring match in DB
        products = db.query(Product).filter(
            Product.merchant_id == merchant_id,
            Product.is_active == True,
        ).all()
        for p in products:
            if p.name in name_lower or name_lower in p.name:
                return p, float(p.price)
                
        return None, None

    def add_or_update_product(
        self,
        db: Session,
        name: str,
        price: float = 0.0,
        category: Optional[str] = "General",
        unit: Optional[str] = None,
        description: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Product:
        """
        Add a new product or update an existing one in the merchant catalog.
        Open schema — any item of any type/category can be added with dynamic attributes.
        """
        import json
        merchant = self.get_or_create_merchant(db)
        clean_name = name.strip().lower()
        
        product = db.query(Product).filter(
            Product.merchant_id == merchant.id,
            Product.name == clean_name
        ).first()

        attrs_str = json.dumps(attributes) if attributes is not None else None

        if product:
            product.price = price if price > 0 else product.price
            if category and category.lower() != "general":
                product.category = category
            if unit:
                product.unit = unit
            if description:
                product.description = description
            if attrs_str is not None:
                product.attributes = attrs_str
            product.is_active = True
        else:
            product = Product(
                merchant_id=merchant.id,
                name=clean_name,
                price=price,
                category=category or "General",
                unit=unit,
                description=description,
                attributes=attrs_str or "{}",
                is_active=True,
            )
            db.add(product)

        db.commit()
        db.refresh(product)
        return product

    def create_sale(self, db: Session, sale_in: SaleCreate) -> Sale:
        merchant = self.get_or_create_merchant(db)
        sale_id = f"sale_{uuid.uuid4().hex[:10]}"
        
        sale = Sale(
            id=sale_id,
            merchant_id=merchant.id,
            customer_name=sale_in.customer_name,
            status="PENDING",
            raw_voice_transcript=sale_in.raw_voice_transcript
        )
        db.add(sale)
        db.flush()

        total_amount = 0.0
        sale_items: List[SaleItem] = []

        for item_data in sale_in.items:
            product, catalog_price = self.find_product_price(db, merchant.id, item_data.product_name)
            # Spoken unit price overrides catalog price
            if item_data.unit_price is not None:
                unit_price = item_data.unit_price
            elif catalog_price is not None:
                unit_price = catalog_price
            else:
                raise ValueError(
                    f"'{item_data.product_name}' aapke catalog me nahi hai aur price bhi nahi bola gaya. "
                    "Pehle item catalog me add karein ya price ke saath bolein."
                )
            subtotal = float(item_data.quantity * unit_price)
            total_amount += subtotal

            sale_item = SaleItem(
                sale_id=sale.id,
                product_id=product.id if product else None,
                product_name=item_data.product_name,
                quantity=item_data.quantity,
                unit_price=unit_price,
                subtotal=subtotal
            )
            db.add(sale_item)
            sale_items.append(sale_item)

        sale.total_amount = total_amount
        sale.received_amount = 0.0
        sale.outstanding_amount = total_amount

        # Generate Razorpay Payment Link for the sale
        if sale_in.auto_create_payment_link and total_amount > 0:
            items_desc = ", ".join([f"{it.quantity}x {it.product_name}" for it in sale_items])
            link_info = razorpay_service.create_payment_link(
                amount=total_amount,
                sale_id=sale.id,
                description=f"Order: {items_desc} - Rs. {total_amount:.2f}"
            )
            sale.razorpay_payment_link_id = link_info.get("id")
            sale.razorpay_payment_link_url = link_info.get("short_url")

        db.commit()
        db.refresh(sale)
        return sale

    def get_sale_by_id(self, db: Session, sale_id: str) -> Optional[Sale]:
        return db.query(Sale).filter(Sale.id == sale_id).first()


sales_service = SalesService()
