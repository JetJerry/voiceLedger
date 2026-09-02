"""
VoiceLedger Agent Tools — Deterministic, Grounded AI Agent Execution Layer.
Instrumented with LangSmith @traceable for deep execution observability.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from langsmith import traceable

from backend.app.models.legacy import LegacyMerchant as Merchant, Product, Sale, LegacyPayment as Payment, Customer
from backend.app.schemas.sale import SaleCreate, SaleItemCreate
from backend.app.services.sales_service import sales_service
from backend.app.services.recovery_service import recovery_service
from backend.app.services.business_presets import get_business_preset

logger = logging.getLogger("voiceledger.agent.tools")


@traceable(name="tool_record_sale", run_type="tool")
def record_sale_tool(
    db: Session,
    merchant_id: int,
    items: List[Dict[str, Any]],
    product_map: Dict[str, Any],
    customer_name: Optional[str] = None,
    is_credit: bool = False,
    raw_voice_transcript: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a formal sale in the merchant ledger, updates stock/catalog pricing,
    and automatically generates a Razorpay payment link/QR if not a credit order.
    """
    sale_items_create = []
    for it in items:
        p_name = str(it.get("product_name", "")).strip()
        if not p_name:
            continue
        qty = int(it.get("quantity", 1) or 1)
        unit_price = it.get("unit_price")

        # Fallback to catalog price if not spoken
        if not unit_price or float(unit_price) <= 0:
            p_info = product_map.get(p_name.lower())
            if p_info:
                unit_price = p_info["price"]

        if not unit_price or float(unit_price) <= 0:
            unit_price = 50.0  # Safe default

        # Auto-register product in merchant catalog if new
        try:
            clean_name = p_name.lower()
            existing_p = db.query(Product).filter(
                Product.merchant_id == merchant_id,
                Product.name == clean_name
            ).first()
            if not existing_p:
                new_p = Product(
                    merchant_id=merchant_id,
                    name=clean_name,
                    price=float(unit_price),
                    category=it.get("category") or "General",
                    unit=it.get("unit") or "item",
                    is_active=True,
                )
                db.add(new_p)
                db.commit()
                # Update local map
                product_map[clean_name] = {"id": new_p.id, "price": float(unit_price)}
        except Exception as exc:
            db.rollback()
            logger.debug("Auto catalog add notice: %s", exc)

        sale_items_create.append(
            SaleItemCreate(
                product_name=p_name,
                quantity=qty,
                unit_price=float(unit_price),
            )
        )

    sale_in = SaleCreate(
        items=sale_items_create,
        customer_name=customer_name,
        raw_voice_transcript=raw_voice_transcript,
        auto_create_payment_link=not is_credit,
    )

    sale = sales_service.create_sale(db, sale_in, merchant_id=merchant_id)
    
    item_names = [f"{it.quantity}x {it.product_name}" for it in sale.items]
    items_str = ", ".join(item_names)
    cust_str = f" for {sale.customer_name}" if sale.customer_name else ""

    if is_credit:
        agent_reply = f"{items_str}{cust_str} ka Rs. {sale.total_amount:.2f} ka udhaar record ho gaya hai."
        action_taken = "CREDIT_RECORDED"
    else:
        rzp_note = " Razorpay QR code aur payment link generate ho gaya hai." if sale.razorpay_payment_link_url else ""
        agent_reply = f"{items_str}{cust_str} ka Rs. {sale.total_amount:.2f} ka sale record ho gaya hai.{rzp_note}"
        action_taken = "SALE_CREATED"

    return {
        "action_taken": action_taken,
        "agent_reply": agent_reply,
        "sale": {
            "id": sale.id,
            "total_amount": sale.total_amount,
            "status": sale.status,
            "customer_name": sale.customer_name,
            "razorpay_payment_link_url": sale.razorpay_payment_link_url,
        },
        "sale_id": sale.id,
        "total_amount": sale.total_amount,
        "status": sale.status,
    }


@traceable(name="tool_check_payment_status", run_type="tool")
def check_payment_status_tool(
    db: Session,
    merchant_id: int,
    product_filter: Optional[str] = None,
    customer_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Queries live transaction ledger and Razorpay webhook state to confirm
    whether payment was received (PAID), partially received (PARTIAL), or still pending (PENDING).
    """
    recent_sales = (
        db.query(Sale)
        .filter(Sale.merchant_id == merchant_id)
        .order_by(Sale.created_at.desc())
        .limit(15)
        .all()
    )
    matched_sale = None

    if product_filter:
        p_name = product_filter.lower().strip()
        for s in recent_sales:
            for item in s.items:
                if p_name in item.product_name.lower():
                    matched_sale = s
                    break
            if matched_sale:
                break

    if not matched_sale and customer_name:
        c_name = customer_name.lower().strip()
        for s in recent_sales:
            if s.customer_name and c_name in s.customer_name.lower():
                matched_sale = s
                break

    if not matched_sale and recent_sales:
        matched_sale = recent_sales[0]

    if matched_sale:
        item_desc = ", ".join(f"{it.quantity}x {it.product_name}" for it in matched_sale.items) or "Order"
        cust_text = f" ({matched_sale.customer_name})" if matched_sale.customer_name else ""

        if matched_sale.status == "PAID":
            agent_reply = f"Haan! {item_desc}{cust_text} ka Rs. {matched_sale.received_amount:.2f} payment receive ho chuka hai (PAID ✅)."
        elif matched_sale.status == "PARTIAL":
            agent_reply = f"{item_desc}{cust_text} ka Rs. {matched_sale.received_amount:.2f} receive hua hai, Rs. {matched_sale.outstanding_amount:.2f} abhi baaki hai (PARTIAL)."
        else:
            agent_reply = f"Nahi, {item_desc}{cust_text} ka Rs. {matched_sale.total_amount:.2f} payment abhi tak pending hai (PENDING)."

        return {
            "action_taken": "PAYMENT_STATUS_CHECKED",
            "agent_reply": agent_reply,
            "matched_sale_id": matched_sale.id,
            "status": matched_sale.status,
            "amount": matched_sale.total_amount,
            "received_amount": matched_sale.received_amount,
            "outstanding_amount": matched_sale.outstanding_amount,
        }
    else:
        return {
            "action_taken": "PAYMENT_STATUS_CHECKED",
            "agent_reply": "Abhi tak koi transaction record nahi mila hai jiska payment check kiya ja sake.",
            "matched_sale_id": None,
            "status": "NONE",
        }


@traceable(name="tool_add_to_catalog", run_type="tool")
def add_to_catalog_tool(
    db: Session,
    merchant_id: int,
    product_name: str,
    unit_price: float,
    category: Optional[str] = None,
    unit: Optional[str] = None,
    extracted_attrs: Optional[Dict[str, Any]] = None,
    business_type: str = "General Retail",
) -> Dict[str, Any]:
    """
    Adds or updates a product in the merchant store catalog with dynamic business attributes.
    """
    prod_name = product_name.strip().lower()
    if unit_price <= 0:
        return {
            "action_taken": "CATALOG_ADD_PRICE_REQUIRED",
            "agent_reply": f"{prod_name.title()} ke liye price bolein (jaise: '{prod_name} 50 rupaye').",
        }

    existing = db.query(Product).filter(
        Product.merchant_id == merchant_id,
        Product.name.ilike(prod_name)
    ).first()

    if existing:
        existing.price = unit_price
        existing.is_active = True
        if extracted_attrs:
            current_attrs = {}
            if isinstance(existing.attributes, str):
                try:
                    current_attrs = json.loads(existing.attributes)
                except Exception:
                    current_attrs = {}
            elif isinstance(existing.attributes, dict):
                current_attrs = dict(existing.attributes)
            current_attrs.update(extracted_attrs)
            existing.attributes = json.dumps(current_attrs)
        db.commit()
        db.refresh(existing)
        return {
            "action_taken": "CATALOG_UPDATED",
            "agent_reply": f"{existing.name.title()} ka price update ho gaya: Rs. {existing.price:.2f}.",
            "product_id": existing.id,
            "name": existing.name,
            "price": existing.price,
        }
    else:
        preset = get_business_preset(business_type)
        cat = category or preset.get("category", "General")
        prod_unit = unit or preset.get("unit", "piece")
        merged_attrs = dict(preset.get("default_attributes", {}))
        if extracted_attrs:
            merged_attrs.update(extracted_attrs)

        new_prod = Product(
            merchant_id=merchant_id,
            name=prod_name,
            price=unit_price,
            category=cat,
            unit=prod_unit,
            attributes=json.dumps(merged_attrs),
            is_active=True,
        )
        db.add(new_prod)
        db.commit()
        db.refresh(new_prod)
        return {
            "action_taken": "CATALOG_ITEM_ADDED",
            "agent_reply": f"Menu me {new_prod.name.title()} add ho gaya: Rs. {new_prod.price:.2f} per {new_prod.unit}.",
            "product_id": new_prod.id,
            "name": new_prod.name,
            "price": new_prod.price,
        }


@traceable(name="tool_query_store_finances", run_type="tool")
def query_store_finances_tool(
    db: Session,
    merchant_id: int,
    intent: str,
) -> Dict[str, Any]:
    """
    Computes real-time financial summaries: daily GMV, total collections, and outstanding debt.
    """
    sales = db.query(Sale).filter(Sale.merchant_id == merchant_id).all()
    total_outstanding = sum(s.outstanding_amount for s in sales)
    today_utc = datetime.now(timezone.utc).date()
    today_sales_list = [
        s for s in sales
        if s.created_at and (s.created_at.date() == today_utc if hasattr(s.created_at, "date") else str(s.created_at)[:10] == str(today_utc))
    ]
    today_gmv = sum(s.total_amount for s in today_sales_list)
    today_collected = sum(s.received_amount for s in today_sales_list)

    if intent == "query_pending":
        agent_reply = f"Aapka kul pending udhaar Rs. {total_outstanding:.2f} hai."
        action_taken = "PENDING_QUERIED"
    else:
        agent_reply = f"Aaj ka total sale Rs. {today_gmv:.2f} hua hai, jisme se Rs. {today_collected:.2f} collect ho chuka hai."
        action_taken = "DAILY_QUERIED"

    return {
        "action_taken": action_taken,
        "agent_reply": agent_reply,
        "total_outstanding": total_outstanding,
        "today_gmv": today_gmv,
        "today_collected": today_collected,
        "total_sales_count": len(sales),
        "today_sales_count": len(today_sales_list),
    }


@traceable(name="tool_list_or_search_catalog", run_type="tool")
def list_or_search_catalog_tool(
    db: Session,
    merchant_id: int,
    intent: str,
    search_query: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Explores the merchant's catalog or searches for specific item prices and details.
    """
    products = db.query(Product).filter(Product.merchant_id == merchant_id, Product.is_active == True).all()
    if not products:
        return {
            "action_taken": "CATALOG_LISTED" if intent == "list_catalog" else "CATALOG_SEARCHED",
            "agent_reply": "Aapke catalog me abhi koi product nahi hai. Pehle 'Add Product' se item add karein ya bolein: 'Menu mein burger add karo 100 rupaye'.",
            "catalog_count": 0,
        }

    if intent == "list_catalog" or not search_query:
        categories = list(dict.fromkeys(p.category or "General" for p in products))
        items_preview = ", ".join(f"{p.name.title()} (Rs. {p.price:.0f})" for p in products[:8])
        more_text = f" aur {len(products) - 8} anya items" if len(products) > 8 else ""
        agent_reply = f"Aapke catalog me kul {len(products)} items hain ({', '.join(categories[:4])}): {items_preview}{more_text}."
        return {
            "action_taken": "CATALOG_LISTED",
            "agent_reply": agent_reply,
            "catalog_count": len(products),
            "categories_count": len(categories),
        }
    else:
        q_name = (search_query or "").lower().strip()
        matches = [p for p in products if q_name and (q_name in p.name.lower() or p.name.lower() in q_name)]
        if matches:
            p = matches[0]
            agent_reply = f"{p.name.title()} ka price Rs. {p.price:.2f} per {p.unit or 'piece'} hai (Category: {p.category or 'General'})."
            return {
                "action_taken": "CATALOG_SEARCHED",
                "agent_reply": agent_reply,
                "product_id": p.id,
                "name": p.name,
                "price": p.price,
                "unit": p.unit,
                "category": p.category,
                "catalog_count": len(products),
            }
        else:
            items_preview = ", ".join(f"{p.name.title()}" for p in products[:5])
            agent_reply = f"Catalog me '{search_query}' nahi mila. Aapke catalog me items hain: {items_preview}."
            return {
                "action_taken": "CATALOG_SEARCHED",
                "agent_reply": agent_reply,
                "catalog_count": len(products),
            }
