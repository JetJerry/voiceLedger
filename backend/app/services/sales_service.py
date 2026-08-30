import uuid
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from backend.app.models import Merchant, Customer, Product, Sale, SaleItem
from backend.app.schemas.sale import SaleCreate
from backend.app.services.razorpay_service import razorpay_service


class SalesService:
    def get_or_create_merchant(self, db: Session) -> Merchant:
        merchant = db.query(Merchant).first()
        if not merchant:
            merchant = Merchant(name="Kirana & Cafe Express", currency="INR")
            db.add(merchant)
            db.commit()
            db.refresh(merchant)
        return merchant

    def get_or_create_customer(self, db: Session, merchant_id: int, name: str, phone: Optional[str] = None) -> Customer:
        name_clean = name.strip()
        customer = db.query(Customer).filter(
            Customer.merchant_id == merchant_id,
            Customer.name.ilike(name_clean)
        ).first()
        
        if not customer:
            customer = Customer(
                merchant_id=merchant_id,
                name=name_clean,
                phone=phone
            )
            db.add(customer)
            db.commit()
            db.refresh(customer)
        elif phone and not customer.phone:
            customer.phone = phone
            db.commit()
            db.refresh(customer)
            
        return customer

    def find_product_price(self, db: Session, merchant_id: int, item_name: str) -> Tuple[Optional[Product], float]:
        """
        Fuzzy matches item name to catalog products.
        Returns matched Product and authoritative unit price.
        """
        name_lower = item_name.strip().lower()
        
        # 1. Exact match
        product = db.query(Product).filter(
            Product.merchant_id == merchant_id,
            Product.name == name_lower
        ).first()
        
        if product:
            return product, float(product.price)
            
        # 2. Substring match
        products = db.query(Product).filter(Product.merchant_id == merchant_id).all()
        for p in products:
            if p.name in name_lower or name_lower in p.name:
                return p, float(p.price)
                
        # 3. Default fallback price if unknown product
        return None, 100.0

    def create_sale(self, db: Session, sale_in: SaleCreate) -> Sale:
        merchant = self.get_or_create_merchant(db)
        customer = self.get_or_create_customer(
            db,
            merchant_id=merchant.id,
            name=sale_in.customer_name,
            phone=sale_in.customer_phone
        )
        
        sale_id = f"sale_{uuid.uuid4().hex[:10]}"
        sale = Sale(
            id=sale_id,
            merchant_id=merchant.id,
            customer_id=customer.id,
            customer_name=customer.name,
            status="PENDING",
            raw_voice_transcript=sale_in.raw_voice_transcript
        )
        db.add(sale)
        db.flush()

        total_amount = 0.0
        sale_items: List[SaleItem] = []

        for item_data in sale_in.items:
            product, catalog_price = self.find_product_price(db, merchant.id, item_data.product_name)
            unit_price = item_data.unit_price if item_data.unit_price is not None else catalog_price
            subtotal = float(item_data.quantity * unit_price)
            total_amount += subtotal

            sale_item = SaleItem(
                sale_id=sale.id,
                product_id=product.id if product else None,
                product_name=product.name if product else item_data.product_name,
                quantity=item_data.quantity,
                unit_price=unit_price,
                subtotal=subtotal
            )
            db.add(sale_item)
            sale_items.append(sale_item)

        sale.total_amount = total_amount
        sale.received_amount = 0.0
        sale.outstanding_amount = total_amount

        # Generate Razorpay Payment Link if requested
        if sale_in.auto_create_payment_link and total_amount > 0:
            link_info = razorpay_service.create_payment_link(
                amount=total_amount,
                sale_id=sale.id,
                customer_name=customer.name,
                customer_phone=customer.phone,
                description=f"Order from {merchant.name} - ₹{total_amount:.2f}"
            )
            sale.razorpay_payment_link_id = link_info.get("id")
            sale.razorpay_payment_link_url = link_info.get("short_url")

        db.commit()
        db.refresh(sale)
        return sale

    def get_sale_by_id(self, db: Session, sale_id: str) -> Optional[Sale]:
        return db.query(Sale).filter(Sale.id == sale_id).first()


sales_service = SalesService()
