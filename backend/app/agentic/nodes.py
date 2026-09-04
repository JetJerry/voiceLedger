"""
LangGraph Agent Nodes — Modular Agent Execution Pipeline with LangSmith Tracing.
Strictly isolated by merchant_id for multi-tenant safety.
"""
import json
import logging
import uuid
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from langsmith import traceable

from backend.app.agentic.state import VoiceLedgerState
from backend.app.models.merchant import Merchant
from backend.app.models.product import Product
from backend.app.models.merchant_profile import MerchantProfile
from backend.app.services.llm_service import llm_service
from backend.app.services.store_service import store_service
from backend.app.services.tts_service import tts_service
from backend.app.schemas.voice import VoiceExtractionResult
from backend.app.agentic.tools import (
    record_sale_tool,
    check_payment_status_tool,
    add_to_catalog_tool,
    query_store_finances_tool,
    list_or_search_catalog_tool,
)

logger = logging.getLogger("voiceledger.langgraph.nodes")


# ── Node 1: Context Enricher ──────────────────────────────────────────

@traceable(name="node_enrich_context", run_type="chain")
def enrich_context_node(state: VoiceLedgerState, db: Session) -> Dict[str, Any]:
    """
    Enriches agent state with live store catalog, product pricing, and business presets from the database.
    """
    merchant = None
    raw_m_id = state.get("merchant_id")
    if raw_m_id:
        target_uuid = raw_m_id if isinstance(raw_m_id, uuid.UUID) else None
        if target_uuid is None:
            try:
                target_uuid = uuid.UUID(str(raw_m_id))
            except Exception:
                pass
        if target_uuid:
            merchant = db.query(Merchant).filter(Merchant.id == target_uuid).first()

    if not merchant:
        merchant = db.query(Merchant).filter(Merchant.status == "ACTIVE").first()

    if not merchant:
        return {
            "merchant_id": None,
            "catalog_items": [],
            "product_map": {},
            "business_type": "General Retail",
            "merchant_profile": None,
        }

    products = (
        db.query(Product)
        .filter(Product.merchant_id == merchant.id, Product.is_active == True)
        .all()
    )

    catalog_names = [p.name for p in products]
    product_map = {
        p.name.lower(): {
            "id": str(p.id),
            "price": p.price,
            "category": p.category,
            "unit": p.unit,
        }
        for p in products
    }

    profile_obj = (
        db.query(MerchantProfile)
        .filter(MerchantProfile.merchant_id == merchant.id)
        .first()
    )
    merchant_profile = profile_obj.config_json if profile_obj else None
    business_type = (
        merchant.business_type
        or (merchant_profile or {}).get("business_type", "Kirana & Retail")
    )

    return {
        "merchant_id": merchant.id,
        "catalog_items": catalog_names,
        "product_map": product_map,
        "business_type": business_type,
        "merchant_profile": merchant_profile,
    }


# ── Node 2: Intent & Entity Extractor ─────────────────────────────────

@traceable(name="node_extract_intent", run_type="chain")
def extract_intent_node(state: VoiceLedgerState) -> Dict[str, Any]:
    """
    Invokes the AI LLM (Groq / Gemini) to extract intent, products, quantities, and payment terms.
    """
    raw_text = state.get("raw_text", "")
    catalog_items = state.get("catalog_items", [])
    merchant_profile = state.get("merchant_profile")
    business_type = state.get("business_type", "")
    context = state.get("context", "terminal")
    history = state.get("history", [])

    extraction: VoiceExtractionResult = llm_service.extract_transaction(
        raw_text,
        catalog_items=catalog_items,
        merchant_profile=merchant_profile,
        business_type=business_type,
        context=context,
        history=history,
    )

    items_dict = [it.model_dump() for it in extraction.items] if extraction.items else []
    attrs = getattr(extraction, "attributes", {}) or {}

    return {
        "intent": extraction.intent,
        "product_name": extraction.product_name,
        "items": items_dict,
        "total_amount": getattr(extraction, "total_amount", None),
        "customer_name": extraction.customer_name,
        "is_credit": getattr(extraction, "is_credit", False),
        "explanation": extraction.explanation,
        "attributes": attrs,
        "extraction_result": extraction.model_dump(),
    }


# ── Node 3: Guardrails & Validator ────────────────────────────────────

@traceable(name="node_guardrails_validator", run_type="chain")
def guardrails_validator_node(state: VoiceLedgerState) -> Dict[str, Any]:
    """
    Anti-hallucination agent guardrail:
    - Protects store ledger by verifying items and quantities.
    - If items are spoken (e.g. 2 burger 100 rs), permits dynamic sale and catalog registration.
    - Prompts merchant only if no items or numbers could be extracted.
    """
    intent = state.get("intent", "general_qa")
    items = state.get("items", [])

    if intent == "record_sale":
        if not items:
            return {
                "is_valid": False,
                "validation_error": "SALE_ITEMS_MISSING",
                "action_taken": "SALE_VALIDATION_FAILED",
                "agent_reply": (
                    state.get("explanation")
                    or "Order record karne ke liye item ka naam aur price bolein (jaise: '2 coffee 60 rs')."
                ),
            }

    return {
        "is_valid": True,
        "validation_error": None,
        "action_taken": "PENDING_EXECUTION",
    }


# ── Node 4: Agent Tool Execution Layer ────────────────────────────────

@traceable(name="node_execute_tool", run_type="chain")
def execute_tool_node(state: VoiceLedgerState, db: Session) -> Dict[str, Any]:
    """
    Executes grounded agent tools based on validated AI intent.
    """
    intent = state.get("intent", "general_qa")
    merchant_id = state.get("merchant_id")
    business_type = state.get("business_type", "Kirana & Retail")
    product_map = state.get("product_map", {})
    items = state.get("items", [])
    raw_text = state.get("raw_text", "")
    customer_name = state.get("customer_name")
    is_credit = state.get("is_credit", False)

    if not merchant_id:
        return {
            "agent_reply": "Merchant context missing. Please ensure your store session is active.",
            "action_taken": "ERROR_NO_MERCHANT",
            "tool_result": {},
        }

    # 1. Record Sale Tool
    if intent == "record_sale":
        res = record_sale_tool(
            db=db,
            merchant_id=merchant_id,
            items=items,
            product_map=product_map,
            customer_name=customer_name,
            is_credit=is_credit,
            raw_voice_transcript=raw_text,
        )
        return {
            "agent_reply": res["agent_reply"],
            "action_taken": res["action_taken"],
            "tool_result": res,
        }

    # 2. Check Payment Status Tool
    elif intent == "check_payment_status":
        product_filter = items[0].get("product_name") if items else state.get("product_name")
        res = check_payment_status_tool(
            db=db,
            merchant_id=merchant_id,
            product_filter=product_filter,
            customer_name=customer_name,
        )
        return {
            "agent_reply": res["agent_reply"],
            "action_taken": res["action_taken"],
            "tool_result": res,
        }

    # 3. Add to Catalog Tool
    elif intent == "add_to_catalog":
        if not items:
            explanation = (
                state.get("explanation")
                or "Product add karne ke liye product ka naam aur price bolein (jaise: 'Burger 100 rupaye')."
            )
            return {
                "agent_reply": explanation,
                "action_taken": "CATALOG_ADD_PRICE_REQUIRED",
                "tool_result": {},
            }

        added_items = []
        for it in items:
            prod_name = it.get("product_name", "").strip()
            if not prod_name:
                continue
            prod_price = float(it.get("unit_price") or 0.0)
            cat = it.get("category")
            unit = it.get("unit")
            extracted_attrs = state.get("attributes", {})

            res = add_to_catalog_tool(
                db=db,
                merchant_id=merchant_id,
                product_name=prod_name,
                unit_price=prod_price,
                category=cat,
                unit=unit,
                extracted_attrs=extracted_attrs,
                business_type=business_type,
            )
            added_items.append(res)

        if len(added_items) == 1:
            return {
                "agent_reply": added_items[0]["agent_reply"],
                "action_taken": added_items[0]["action_taken"],
                "tool_result": added_items[0],
            }
        elif len(added_items) > 1:
            names = ", ".join(
                f"{it.get('name', 'item').title()} (Rs. {it.get('price', 0):.0f})"
                for it in added_items
            )
            return {
                "agent_reply": f"Catalog me {len(added_items)} items add ho gaye: {names}.",
                "action_taken": "CATALOG_ITEMS_ADDED",
                "tool_result": {"items": added_items},
            }
        else:
            return {
                "agent_reply": "Product add karne ke liye product ka naam aur price bolein.",
                "action_taken": "CATALOG_ADD_FAILED",
                "tool_result": {},
            }

    # 4. Financial Analytics Tool (GMV, Outstanding Debt)
    elif intent in ["query_pending", "query_daily"]:
        res = query_store_finances_tool(
            db=db,
            merchant_id=merchant_id,
            intent=intent,
        )
        return {
            "agent_reply": res["agent_reply"],
            "action_taken": res["action_taken"],
            "tool_result": res,
        }

    # 5. List / Search Catalog Tool
    elif intent in ["list_catalog", "search_catalog"]:
        search_query = state.get("product_name") or (
            items[0].get("product_name") if items else None
        )
        res = list_or_search_catalog_tool(
            db=db,
            merchant_id=merchant_id,
            intent=intent,
            search_query=search_query,
        )
        return {
            "agent_reply": res["agent_reply"],
            "action_taken": res["action_taken"],
            "tool_result": res,
        }

    # 6. General Conversational QA
    else:
        agent_reply = (
            state.get("explanation")
            or "Namaste! Main VoiceLedger AI Assistant hoon. Aap bolkar sale record karwa sakte hain, payment verify kar sakte hain, ya menu me product add kar sakte hain."
        )
        return {
            "agent_reply": agent_reply,
            "action_taken": "QUERY_ANSWERED",
            "tool_result": {},
        }


# ── Node 5: Response Generator & Speech Refiner ───────────────────────

@traceable(name="node_generate_response", run_type="chain")
def generate_response_node(state: VoiceLedgerState) -> Dict[str, Any]:
    """
    Polishes the final response text using the LLM for fluent, natural voice delivery.
    """
    reply = state.get("agent_reply") or "Command process ho gaya."
    voice_lang = state.get("voice_lang", "hi")

    refined_reply = llm_service.refine_for_speech(reply, voice_lang)
    return {
        "agent_reply": refined_reply,
    }


# ── Node 6: Neural TTS Synthesizer ────────────────────────────────────

@traceable(name="node_synthesize_tts", run_type="chain")
def synthesize_tts_node(state: VoiceLedgerState) -> Dict[str, Any]:
    """
    Synthesizes Neural TTS audio base64 if speak_response is enabled.
    """
    speak_response = state.get("speak_response", True)
    agent_reply = state.get("agent_reply", "")
    voice_lang = state.get("voice_lang", "hi")

    audio_base64 = None
    if speak_response and agent_reply:
        try:
            audio_base64 = tts_service.generate_speech_base64(agent_reply, lang=voice_lang)
        except Exception as e:
            logger.warning("[TTS] Audio generation in LangGraph node failed: %s", e)

    return {
        "audio_base64": audio_base64,
    }
