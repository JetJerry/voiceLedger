"""
VoiceLedger Store Service.

Authoritative domain service for Product Catalog, Inventory Stock Management,
Sales Order Ledger, and Razorpay payment integration within strict tenant boundaries.
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.app.models.product import Product
from backend.app.models.sale import Sale, SaleItem
from backend.app.models.merchant import Merchant
from backend.app.models.merchant_profile import MerchantProfile
from backend.app.models.payment import Payment, PaymentStatus
from backend.app.schemas.sale import (
    ProductCreate,
    ProductUpdate,
    SaleCreate,
    InventoryAdjustResponse,
)
from backend.app.services.business_presets import get_business_preset, BUSINESS_TYPES
from backend.app.config import settings

logger = logging.getLogger("voiceledger.store.service")


class StoreService:
    """Manages merchant-scoped store operations."""

    # ── 1. Catalog Products ──────────────────────────────────────────

    def list_products(
        self,
        db: Session,
        merchant_id: uuid.UUID,
        category: Optional[str] = None,
        search: Optional[str] = None,
        active_only: bool = True,
    ) -> List[Product]:
        """List catalog products strictly scoped to merchant_id."""
        query = db.query(Product).filter(Product.merchant_id == merchant_id)

        if active_only:
            query = query.filter(Product.is_active == True)

        if category and category.upper() != "ALL":
            query = query.filter(Product.category.ilike(f"%{category.strip()}%"))

        if search:
            term = f"%{search.strip().lower()}%"
            query = query.filter(
                or_(
                    Product.name.ilike(term),
                    Product.category.ilike(term),
                    Product.description.ilike(term),
                )
            )

        return query.order_by(Product.category.asc(), Product.name.asc()).all()

    def get_product(
        self,
        db: Session,
        merchant_id: uuid.UUID,
        product_id: uuid.UUID,
    ) -> Optional[Product]:
        """Retrieve single product enforcing merchant tenant boundary."""
        return (
            db.query(Product)
            .filter(Product.id == product_id, Product.merchant_id == merchant_id)
            .first()
        )

    def create_product(
        self,
        db: Session,
        merchant_id: uuid.UUID,
        product_in: ProductCreate,
    ) -> Product:
        """Add product to merchant catalog with deduplication by name."""
        clean_name = product_in.name.strip().lower()
        existing = (
            db.query(Product)
            .filter(
                Product.merchant_id == merchant_id,
                Product.name == clean_name,
            )
            .first()
        )

        price_minor = int(round(product_in.price * 100))

        if existing:
            existing.price_minor = price_minor
            existing.category = product_in.category or existing.category
            existing.description = product_in.description or existing.description
            existing.unit = product_in.unit or existing.unit
            existing.stock_quantity = product_in.stock_quantity
            existing.track_inventory = product_in.track_inventory
            if product_in.attributes:
                existing.attributes = product_in.attributes
            existing.is_active = True
            existing.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(existing)
            logger.info("Updated existing product %s for merchant %s", existing.id, merchant_id)
            return existing

        product = Product(
            id=uuid.uuid4(),
            merchant_id=merchant_id,
            name=clean_name,
            price_minor=price_minor,
            category=product_in.category or "General",
            description=product_in.description,
            unit=product_in.unit or "piece",
            stock_quantity=product_in.stock_quantity,
            track_inventory=product_in.track_inventory,
            attributes=product_in.attributes or {},
            is_active=True,
        )
        db.add(product)
        db.commit()
        db.refresh(product)
        logger.info("Created new product %s ('%s') for merchant %s", product.id, product.name, merchant_id)
        return product

    def bulk_create_products(
        self,
        db: Session,
        merchant_id: uuid.UUID,
        products: List[ProductCreate],
    ) -> List[Product]:
        """Bulk add or update products in catalog."""
        results = []
        for p in products:
            prod = self.create_product(db, merchant_id, p)
            results.append(prod)
        return results

    def update_product(
        self,
        db: Session,
        merchant_id: uuid.UUID,
        product_id: uuid.UUID,
        update: ProductUpdate,
    ) -> Optional[Product]:
        """Update an existing product with tenant isolation."""
        product = self.get_product(db, merchant_id, product_id)
        if not product:
            return None

        update_dict = update.model_dump(exclude_unset=True)
        for field, val in update_dict.items():
            if field == "name" and val:
                product.name = str(val).strip().lower()
            elif field == "price" and val is not None:
                product.price_minor = int(round(float(val) * 100))
            elif hasattr(product, field):
                setattr(product, field, val)

        product.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(product)
        return product

    def delete_product(
        self,
        db: Session,
        merchant_id: uuid.UUID,
        product_id: uuid.UUID,
    ) -> bool:
        """Soft-deactivate product."""
        product = self.get_product(db, merchant_id, product_id)
        if not product:
            return False

        product.is_active = False
        product.updated_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("Deactivated product %s for merchant %s", product_id, merchant_id)
        return True

    # ── 2. Inventory Management ──────────────────────────────────────

    def adjust_stock(
        self,
        db: Session,
        merchant_id: uuid.UUID,
        product_id: uuid.UUID,
        delta: int,
        reason: str = "manual_adjustment",
    ) -> Optional[InventoryAdjustResponse]:
        """Adjust product stock quantity with audit."""
        product = self.get_product(db, merchant_id, product_id)
        if not product:
            return None

        prev_qty = product.stock_quantity
        new_qty = max(0, prev_qty + delta)
        product.stock_quantity = new_qty
        product.track_inventory = True
        product.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(product)

        logger.info(
            "Stock adjusted for product %s (%s): %d -> %d (delta: %d, reason: %s)",
            product.id,
            product.name,
            prev_qty,
            new_qty,
            delta,
            reason,
        )

        return InventoryAdjustResponse(
            product_id=product.id,
            product_name=product.name,
            previous_quantity=prev_qty,
            new_quantity=new_qty,
            delta=delta,
            reason=reason,
        )

    # ── 3. Sales & Orders Ledger ─────────────────────────────────────

    def create_sale(
        self,
        db: Session,
        merchant_id: uuid.UUID,
        sale_in: SaleCreate,
    ) -> Sale:
        """
        Creates a canonical Sale with line items.
        If auto_create_payment_link=True, creates a Razorpay payment link.
        Deducts stock for items with track_inventory=True.
        """
        sale_id = f"sale_{uuid.uuid4().hex[:10]}"
        sale = Sale(
            id=sale_id,
            merchant_id=merchant_id,
            customer_name=sale_in.customer_name.strip() if sale_in.customer_name else None,
            customer_phone=sale_in.customer_phone.strip() if sale_in.customer_phone else None,
            raw_voice_transcript=sale_in.raw_voice_transcript,
            status="PENDING",
        )
        db.add(sale)

        total_minor = 0
        sale_items = []

        for item_in in sale_in.items:
            # Resolve product if possible
            prod = None
            if item_in.product_id:
                prod = self.get_product(db, merchant_id, item_in.product_id)
            if not prod:
                clean_name = item_in.product_name.strip().lower()
                prod = (
                    db.query(Product)
                    .filter(
                        Product.merchant_id == merchant_id,
                        Product.name == clean_name,
                    )
                    .first()
                )

            # Price determination
            unit_price_minor = 0
            if item_in.unit_price is not None and item_in.unit_price > 0:
                unit_price_minor = int(round(item_in.unit_price * 100))
            elif prod:
                unit_price_minor = prod.price_minor
            else:
                unit_price_minor = 5000  # Default 50 INR fallback

            subtotal_minor = unit_price_minor * max(1, item_in.quantity)
            total_minor += subtotal_minor

            item = SaleItem(
                id=uuid.uuid4(),
                sale_id=sale_id,
                product_id=prod.id if prod else None,
                product_name=item_in.product_name.strip(),
                quantity=max(1, item_in.quantity),
                unit_price_minor=unit_price_minor,
                subtotal_minor=subtotal_minor,
            )
            sale_items.append(item)

            # Deduct stock if tracked
            if prod and prod.track_inventory:
                prod.stock_quantity = max(0, prod.stock_quantity - item.quantity)

        sale.total_amount_minor = total_minor
        sale.received_amount_minor = 0
        sale.outstanding_amount_minor = total_minor
        sale.items = sale_items

        # Attempt Razorpay Payment Link creation if requested
        if sale_in.auto_create_payment_link and total_minor > 0:
            link_id, link_url = self._create_razorpay_payment_link(
                merchant_id=merchant_id,
                sale_id=sale_id,
                amount_minor=total_minor,
                customer_name=sale.customer_name,
                customer_phone=sale.customer_phone,
            )
            sale.razorpay_payment_link_id = link_id
            sale.razorpay_payment_link_url = link_url

        db.commit()
        db.refresh(sale)
        logger.info(
            "Created Sale %s (total: Rs. %.2f, items: %d) for merchant %s",
            sale.id,
            sale.total_amount,
            len(sale_items),
            merchant_id,
        )
        return sale

    def get_sale(
        self,
        db: Session,
        merchant_id: uuid.UUID,
        sale_id: str,
    ) -> Optional[Sale]:
        """Get sale strictly scoped to merchant."""
        return (
            db.query(Sale)
            .filter(Sale.id == sale_id, Sale.merchant_id == merchant_id)
            .first()
        )

    def list_sales(
        self,
        db: Session,
        merchant_id: uuid.UUID,
        limit: int = 50,
        status: Optional[str] = None,
    ) -> List[Sale]:
        """List recent sales for merchant."""
        query = db.query(Sale).filter(Sale.merchant_id == merchant_id)
        if status and status.upper() != "ALL":
            query = query.filter(Sale.status == status.upper())
        return query.order_by(Sale.created_at.desc()).limit(limit).all()

    def _create_razorpay_payment_link(
        self,
        merchant_id: uuid.UUID,
        sale_id: str,
        amount_minor: int,
        customer_name: Optional[str] = None,
        customer_phone: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Creates a real Razorpay payment link via Razorpay client if keys are configured.
        Embeds merchant_id and sale_id in notes for server-side webhook reconciliation.
        """
        if not (settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET):
            return None, None

        try:
            import razorpay
            client = razorpay.Client(
                auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
            )

            link_payload = {
                "amount": amount_minor,
                "currency": "INR",
                "accept_partial": False,
                "description": f"Payment for Order {sale_id}",
                "reference_id": sale_id,
                "notes": {
                    "merchant_id": str(merchant_id),
                    "sale_id": sale_id,
                },
            }
            if customer_name or customer_phone:
                cust: Dict[str, str] = {}
                if customer_name:
                    cust["name"] = customer_name
                if customer_phone:
                    cust["contact"] = customer_phone
                link_payload["customer"] = cust

            resp = client.payment_link.create(link_payload)
            link_id = resp.get("id")
            link_url = resp.get("short_url")
            logger.info("Generated Razorpay Payment Link %s -> %s", link_id, link_url)
            return link_id, link_url
        except Exception as exc:
            logger.warning("Failed to create live Razorpay payment link for sale %s: %s", sale_id, exc)
            return None, None

    # ── 4. Payment to Sale Synchronization ───────────────────────────

    def sync_payment_to_sale(
        self,
        db: Session,
        payment: Payment,
        sale_id: Optional[str] = None,
    ) -> Optional[Sale]:
        """
        Atomically synchronizes a verified canonical Payment with its corresponding Sale.
        Called when webhook captures payment.
        """
        target_sale: Optional[Sale] = None

        if sale_id:
            target_sale = self.get_sale(db, payment.merchant_id, sale_id)

        # Match by razorpay order or payment link if not found
        if not target_sale and payment.provider_order_id:
            target_sale = (
                db.query(Sale)
                .filter(
                    Sale.merchant_id == payment.merchant_id,
                    Sale.razorpay_order_id == payment.provider_order_id,
                )
                .first()
            )

        if not target_sale:
            return None

        # Link Payment
        target_sale.payment_id = payment.id
        if payment.status == PaymentStatus.CAPTURED.value:
            target_sale.status = "PAID"
            target_sale.received_amount_minor = min(
                target_sale.total_amount_minor, payment.amount_minor
            )
            target_sale.outstanding_amount_minor = max(
                0, target_sale.total_amount_minor - target_sale.received_amount_minor
            )
        elif payment.status == PaymentStatus.FAILED.value:
            target_sale.status = "FAILED"

        target_sale.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(target_sale)
        logger.info(
            "Synchronized Payment %s with Sale %s (New status: %s)",
            payment.id,
            target_sale.id,
            target_sale.status,
        )
        return target_sale

    # ── 5. Business Profile & Presets ────────────────────────────────

    def get_merchant_profile(
        self,
        db: Session,
        merchant_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """Fetch merchant profile configuration."""
        profile = (
            db.query(MerchantProfile)
            .filter(MerchantProfile.merchant_id == merchant_id)
            .first()
        )
        if not profile:
            merchant = db.query(Merchant).filter(Merchant.id == merchant_id).first()
            btype = merchant.business_type if merchant else "Kirana & Retail"
            preset = get_business_preset(btype)
            return {
                "business_type": btype,
                "suggested_categories": preset.get("default_categories", []),
                "suggested_units": preset.get("default_units", []),
                "attribute_hints": preset.get("attribute_hints", []),
            }
        return profile.config_json or {}

    def upsert_merchant_profile(
        self,
        db: Session,
        merchant_id: uuid.UUID,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create or update merchant dynamic profile."""
        profile = (
            db.query(MerchantProfile)
            .filter(MerchantProfile.merchant_id == merchant_id)
            .first()
        )
        if not profile:
            profile = MerchantProfile(
                id=uuid.uuid4(),
                merchant_id=merchant_id,
                config_json=config or {},
            )
            db.add(profile)
        else:
            profile.config_json = config or {}
            profile.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(profile)
        return profile.config_json

    def set_business_type(
        self,
        db: Session,
        merchant_id: uuid.UUID,
        business_type: str,
        seed_sample_items: bool = False,
    ) -> Dict[str, Any]:
        """Update business type and optionally seed starter catalog items."""
        merchant = db.query(Merchant).filter(Merchant.id == merchant_id).first()
        if merchant:
            merchant.business_type = business_type
            merchant.updated_at = datetime.now(timezone.utc)

        preset = get_business_preset(business_type)
        cfg = {
            "business_type": business_type,
            "suggested_categories": preset.get("default_categories", []),
            "suggested_units": preset.get("default_units", []),
            "attribute_hints": preset.get("attribute_hints", []),
        }
        self.upsert_merchant_profile(db, merchant_id, cfg)

        seeded_count = 0
        if seed_sample_items:
            for item in preset.get("sample_items", []):
                self.create_product(
                    db,
                    merchant_id,
                    ProductCreate(
                        name=item["name"],
                        price=float(item.get("price", 0)),
                        category=item.get("category", "General"),
                        unit=item.get("unit", "piece"),
                    ),
                )
                seeded_count += 1

        db.commit()
        return {
            "business_type": business_type,
            "preset": preset,
            "seeded_count": seeded_count,
        }


store_service = StoreService()
