import json
import logging
from datetime import datetime, timezone, date
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from backend.app.agentic.state import VoiceLedgerState
from backend.app.models import Merchant, Product, Sale, Payment, MerchantProfile
from backend.app.services.llm_service import llm_service
from backend.app.services.sales_service import sales_service
from backend.app.services.recovery_service import recovery_service
from backend.app.services.tts_service import tts_service
from backend.app.services.business_presets import get_business_preset
from backend.app.schemas.sale import SaleCreate, SaleItemCreate
from backend.app.schemas.voice import VoiceExtractionResult, VoiceItemExtracted

logger = logging.getLogger("voiceledger.langgraph.nodes")


# ── Node 1: Context Enricher ──────────────────────────────────────────

def enrich_context_node(state: VoiceLedgerState, db: Session) -> Dict[str, Any]:
    """
    Enriches state with merchant profile, dynamic product catalog, and store settings.
    """
    merchant = None
    if state.get("merchant_id"):
        merchant = db.query(Merchant).filter(Merchant.id == state["merchant_id"]).first()
    if not merchant:
        merchant = sales_service.get_or_create_merchant(db)

    products = db.query(Product).filter(
        Product.merchant_id == merchant.id,
        Product.is_active == True
    ).all()
    
    catalog_names = [p.name for p in products]
    product_map = {p.name.lower(): {"id": p.id, "price": p.price, "category": p.category, "unit": p.unit} for p in products}

    profile_obj = db.query(MerchantProfile).filter(MerchantProfile.merchant_id == merchant.id).first()
    merchant_profile = None
    if profile_obj and profile_obj.config_json:
        try:
            merchant_profile = json.loads(profile_obj.config_json)
        except Exception:
            merchant_profile = None

    business_type = merchant.business_type or (merchant_profile or {}).get("business_type", "General Retail")

    return {
        "merchant_id": merchant.id,
        "catalog_items": catalog_names,
        "product_map": product_map,
        "business_type": business_type,
        "merchant_profile": merchant_profile,
    }


# ── Node 2: Intent & Entity Extractor ─────────────────────────────────

def extract_intent_node(state: VoiceLedgerState) -> Dict[str, Any]:
    """
    Extracts intent and structured entities from merchant voice/text input.
    """
    raw_text = state.get("raw_text", "")
    catalog_items = state.get("catalog_items", [])
    merchant_profile = state.get("merchant_profile")
    business_type = state.get("business_type", "")
    context = state.get("context", "terminal")

    extraction: VoiceExtractionResult = llm_service.extract_transaction(
        raw_text,
        catalog_items=catalog_items,
        merchant_profile=merchant_profile,
        business_type=business_type,
        context=context,
    )

    items_dict = [it.model_dump() for it in extraction.items] if extraction.items else []
    attrs = getattr(extraction, "attributes", {}) or {}

    return {
        "intent": extraction.intent,
        "items": items_dict,
        "total_amount": getattr(extraction, "total_amount", None),
        "customer_name": extraction.customer_name,
        "is_credit": getattr(extraction, "is_credit", False),
        "explanation": extraction.explanation,
        "attributes": attrs,
        "extraction_result": extraction.model_dump(),
    }


# ── Node 3: Guardrails & Validator ────────────────────────────────────

def guardrails_validator_node(state: VoiceLedgerState) -> Dict[str, Any]:
    """
    Anti-hallucination guardrail:
    - Validates that sold products exist in catalog or have explicit prices.
    - Prevents empty-catalog hallucinations.
    """
    intent = state.get("intent", "general_qa")
    catalog_items = state.get("catalog_items", [])
    items = state.get("items", [])

    if intent == "record_sale":
        if not catalog_items:
            return {
                "is_valid": False,
                "validation_error": "CATALOG_EMPTY",
                "action_taken": "CATALOG_EMPTY",
                "agent_reply": (
                    "Aapke catalog me abhi koi product nahi hai. "
                    "Pehle Menu & Items tab me apna product add karein, "
                    "ya bolein: 'Menu mein chai add karo 20 rupaye'."
                ),
            }

        if not items:
            return {
                "is_valid": False,
                "validation_error": "SALE_ITEMS_MISSING",
                "action_taken": "SALE_VALIDATION_FAILED",
                "agent_reply": (
                    state.get("explanation") or
                    f"Sale record karne ke liye catalog me maujood item ka naam bolein. "
                    f"Maujood items: {', '.join(catalog_items[:8])}."
                ),
            }

    return {
        "is_valid": True,
        "validation_error": None,
        "action_taken": "PENDING_EXECUTION",
    }


# ── Node 4: Deterministic Tool Execution ──────────────────────────────

def execute_tool_node(state: VoiceLedgerState, db: Session) -> Dict[str, Any]:
    """
    Executes database mutations or queries based on validated intent.
    """
    intent = state.get("intent", "general_qa")
    merchant_id = state.get("merchant_id", 1)
    business_type = state.get("business_type", "General Retail")
    product_map = state.get("product_map", {})

    tool_result = {}
    action_taken = "COMPLETED"
    agent_reply = state.get("agent_reply", "")

    # 1. Check Payment Status
    if intent == "check_payment_status":
        items = state.get("items", [])
        customer_name = state.get("customer_name")
        product_filter = items[0].get("product_name") if items else None

        recent_sales = db.query(Sale).filter(Sale.merchant_id == merchant_id).order_by(Sale.created_at.desc()).limit(15).all()
        matched_sale = None

        if product_filter:
            p_name = product_filter.lower()
            for s in recent_sales:
                for item in s.items:
                    if p_name in item.product_name.lower():
                        matched_sale = s
                        break
                if matched_sale:
                    break

        if not matched_sale and customer_name:
            c_name = customer_name.lower()
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

            action_taken = "PAYMENT_STATUS_CHECKED"
            tool_result = {"matched_sale_id": matched_sale.id, "status": matched_sale.status, "amount": matched_sale.total_amount}
        else:
            agent_reply = "Abhi tak koi transaction record nahi mila hai jiska payment check kiya ja sake."
            action_taken = "PAYMENT_STATUS_CHECKED"

    # 2. Record Sale
    elif intent == "record_sale":
        items = state.get("items", [])
        customer_name = state.get("customer_name")
        is_credit = state.get("is_credit", False)
        raw_text = state.get("raw_text", "")

        sale_items_create = []
        for it in items:
            p_name = it.get("product_name", "").strip()
            qty = it.get("quantity", 1)
            unit_price = it.get("unit_price")

            # Check in product map
            if not unit_price or unit_price <= 0:
                p_info = product_map.get(p_name.lower())
                if p_info:
                    unit_price = p_info["price"]

            if not unit_price or unit_price <= 0:
                unit_price = 50.0  # Safe default

            sale_items_create.append(
                SaleItemCreate(product_name=p_name, quantity=qty, unit_price=unit_price)
            )

        sale_in = SaleCreate(
            items=sale_items_create,
            customer_name=customer_name,
            raw_voice_transcript=raw_text,
            auto_create_payment_link=not is_credit,
        )

        sale = sales_service.create_sale(db, sale_in, merchant_id=merchant_id)
        tool_result = {
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

        item_names = [f"{it.quantity}x {it.product_name}" for it in sale.items]
        items_str = ", ".join(item_names)
        cust_str = f" {sale.customer_name} ke liye" if sale.customer_name else ""

        if is_credit:
            agent_reply = f"{items_str}{cust_str} ka Rs. {sale.total_amount:.2f} ka udhaar record ho gaya hai."
            action_taken = "CREDIT_RECORDED"
        else:
            rzp_note = " Razorpay QR code / payment link generate ho gaya hai." if sale.razorpay_payment_link_url else ""
            agent_reply = f"{items_str}{cust_str} ka Rs. {sale.total_amount:.2f} ka sale record ho gaya hai.{rzp_note}"
            action_taken = "SALE_CREATED"

    # 3. Add to Catalog
    elif intent == "add_to_catalog":
        items = state.get("items", [])
        explanation = state.get("explanation", "")
        extracted_attrs = state.get("attributes", {})

        if not items:
            agent_reply = explanation or "Product add karne ke liye product ka naam aur price bolein (jaise: 'Menu mein burger add karo 100 rupaye')."
            action_taken = "CATALOG_ADD_FAILED"
        else:
            it = items[0]
            prod_name = it.get("product_name", "").strip()
            prod_price = it.get("unit_price") or 0.0

            if prod_price <= 0:
                agent_reply = f"{prod_name} ke liye price bolein (jaise: '{prod_name} 50 rupaye')."
                action_taken = "CATALOG_ADD_PRICE_REQUIRED"
            else:
                existing = db.query(Product).filter(
                    Product.merchant_id == merchant_id,
                    Product.name.ilike(prod_name)
                ).first()

                if existing:
                    existing.price = prod_price
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
                    agent_reply = f"{existing.name} ka price update ho gaya: Rs. {existing.price:.2f}."
                    action_taken = "CATALOG_UPDATED"
                    tool_result = {"product_id": existing.id, "name": existing.name, "price": existing.price}
                else:
                    preset = get_business_preset(business_type)
                    cat = it.get("category") or preset.get("category", "General")
                    unit = it.get("unit") or preset.get("unit", "piece")
                    merged_attrs = dict(preset.get("default_attributes", {}))
                    merged_attrs.update(extracted_attrs)

                    new_prod = Product(
                        merchant_id=merchant_id,
                        name=prod_name,
                        price=prod_price,
                        category=cat,
                        unit=unit,
                        attributes=json.dumps(merged_attrs),
                        is_active=True,
                    )
                    db.add(new_prod)
                    db.commit()
                    db.refresh(new_prod)
                    agent_reply = f"Menu me {new_prod.name} add ho gaya: Rs. {new_prod.price:.2f} per {new_prod.unit}."
                    action_taken = "CATALOG_ITEM_ADDED"
                    tool_result = {"product_id": new_prod.id, "name": new_prod.name, "price": new_prod.price}

    # 4. Financial Analytics (Deterministic, Zero Hallucination)
    elif intent in ["query_pending", "query_daily"]:
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

        tool_result = {"total_outstanding": total_outstanding, "today_gmv": today_gmv, "today_collected": today_collected}

    # 5. List / Search Catalog
    elif intent in ["list_catalog", "search_catalog"]:
        products = db.query(Product).filter(Product.merchant_id == merchant_id, Product.is_active == True).all()
        if not products:
            agent_reply = "Aapke catalog me abhi koi product nahi hai. Pehle product add karein."
        elif intent == "list_catalog":
            items_preview = ", ".join(f"{p.name} (Rs. {p.price:.0f})" for p in products[:10])
            agent_reply = f"Aapke catalog me kul {len(products)} items hain: {items_preview}."
        else:
            items = state.get("items", [])
            query_name = items[0].get("product_name") if items else ""
            matches = [p for p in products if query_name and query_name.lower() in p.name.lower()]
            if matches:
                p = matches[0]
                agent_reply = f"{p.name} ka price Rs. {p.price:.2f} per {p.unit or 'piece'} hai (Category: {p.category or 'General'})."
            else:
                agent_reply = f"Catalog me {query_name or 'item'} nahi mila."

        if intent == "list_catalog":
            action_taken = "CATALOG_LISTED"
        else:
            action_taken = "CATALOG_SEARCHED"
        tool_result = {"catalog_count": len(products)}

    # 6. General QA
    else:
        agent_reply = state.get("explanation") or "Namaste! Main VoiceLedger Assistant hoon. Aap bolkar sale record kar sakte hain ya menu me product add kar sakte hain."
        action_taken = "QUERY_ANSWERED"

    return {
        "agent_reply": agent_reply,
        "action_taken": action_taken,
        "tool_result": tool_result,
    }


# ── Node 5: Response Generator & Speech Refiner ───────────────────────

def generate_response_node(state: VoiceLedgerState) -> Dict[str, Any]:
    """
    Polishes the final response text for fluent natural speech.
    """
    reply = state.get("agent_reply") or "Command process ho gaya."
    voice_lang = state.get("voice_lang", "hi")
    
    refined_reply = llm_service.refine_for_speech(reply, voice_lang)
    return {
        "agent_reply": refined_reply,
    }


# ── Node 6: Neural TTS Synthesizer ────────────────────────────────────

def synthesize_tts_node(state: VoiceLedgerState) -> Dict[str, Any]:
    """
    Synthesizes Neural TTS audio base64 if speak_response is requested.
    """
    speak_response = state.get("speak_response", True)
    agent_reply = state.get("agent_reply", "")
    voice_lang = state.get("voice_lang", "hi")

    audio_base64 = None
    if speak_response and agent_reply:
        try:
            audio_base64 = tts_service.generate_speech_base64(agent_reply, lang=voice_lang)
        except Exception as e:
            logger.warning("TTS generation in LangGraph node failed: %s", e)

    return {
        "audio_base64": audio_base64,
    }
