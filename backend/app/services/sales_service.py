import uuid
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from backend.app.models import Merchant, Product, Sale, SaleItem
from backend.app.schemas.sale import SaleCreate
from backend.app.services.razorpay_service import razorpay_service


class SalesService:
    def get_or_create_merchant(self, db: Session) -> Merchant:
        merchant = db.query(Merchant).first()
        if not merchant:
            merchant = Merchant(name="VoiceLedger Merchant", currency="INR")
            db.add(merchant)
            db.commit()
            db.refresh(merchant)
        return merchant

    def find_product_price(self, db: Session, merchant_id: int, item_name: str) -> Tuple[Optional[Product], float]:
        """
        Dynamically matches item name to products table in the database.
        """
        name_lower = item_name.strip().lower()
        
        # 1. Exact match in DB
        product = db.query(Product).filter(
            Product.merchant_id == merchant_id,
            Product.name == name_lower
        ).first()
        if product:
            return product, float(product.price)
            
        # 2. Substring match in DB
        products = db.query(Product).filter(Product.merchant_id == merchant_id).all()
        for p in products:
            if p.name in name_lower or name_lower in p.name:
                return p, float(p.price)
                
        # 3. Default unit price if uncataloged item and not specified in speech
        return None, 50.0

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
            unit_price = item_data.unit_price if item_data.unit_price is not None else catalog_price
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
