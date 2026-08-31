import json
from datetime import datetime, timezone, date
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from backend.app.models import Product, Sale, Payment, MerchantProfile
from backend.app.schemas.voice import VoiceProcessRequest, VoiceProcessResponse, VoiceItemExtracted
from backend.app.schemas.sale import SaleCreate, SaleItemCreate
from backend.app.services.llm_service import llm_service
from backend.app.services.sales_service import sales_service
from backend.app.services.recovery_service import recovery_service
from backend.app.services.tts_service import tts_service
from backend.app.services.business_presets import get_business_preset


class MerchantAgent:
    def _speak(self, text: str, request: VoiceProcessRequest) -> Optional[str]:
        if not request.speak_response:
            return None
        refined = llm_service.refine_for_speech(text, request.voice_lang)
        return tts_service.generate_speech_base64(refined, lang=request.voice_lang)

    def process_merchant_command(self, db: Session, request: VoiceProcessRequest) -> VoiceProcessResponse:
        """
        Guarded Agent Orchestrator:
        - Passes active merchant catalog to LLM with anti-hallucination validation.
        - Uses deterministic DB-grounded answers for financial queries.
        - Generates LLM-refined neural TTS speech audio.
        """
        merchant = sales_service.get_or_create_merchant(db)

        products = db.query(Product).filter(Product.merchant_id == merchant.id, Product.is_active == True).all()
        catalog_names = [p.name for p in products]
        product_map = {p.name: p for p in products}

        profile_obj = db.query(MerchantProfile).filter(MerchantProfile.merchant_id == merchant.id).first()
        merchant_profile = None
        if profile_obj:
            try:
                merchant_profile = json.loads(profile_obj.config_json or "{}")
            except Exception:
                merchant_profile = None

        business_type = merchant.business_type or (merchant_profile or {}).get("business_type")

        extraction = llm_service.extract_transaction(
            request.text,
            catalog_items=catalog_names,
            merchant_profile=merchant_profile,
            business_type=business_type,
            context=request.context or "terminal",
        )
        intent = extraction.intent

        # ── Payment status (DB-grounded, no wrong-sale fallback) ──
        if intent == "check_payment_status":
            return self._handle_payment_status(db, merchant.id, extraction, request)

        # ── List catalog ──
        if intent == "list_catalog":
            return self._handle_list_catalog(products, extraction, request)

        # ── Search catalog item ──
        if intent == "search_catalog":
            return self._handle_search_catalog(products, extraction, request)

        # ── Record sale (requires catalog items) ──
        if intent == "record_sale":
            if not catalog_names:
                agent_reply = (
                    "Aapke catalog me abhi koi product nahi hai. "
                    "Pehle Menu & Items tab me apna product add karein, "
                    "ya bolein: 'Menu mein chai add karo 20 rupaye'."
                )
                return VoiceProcessResponse(
                    extraction=extraction,
                    agent_reply=agent_reply,
                    audio_base64=self._speak(agent_reply, request),
                    action_taken="CATALOG_EMPTY",
                )

            if not extraction.items:
                agent_reply = extraction.explanation or (
                    "Sale record karne ke liye catalog me maujood item ka naam bolein. "
                    f"Maujood items: {', '.join(catalog_names[:10])}."
                )
                return VoiceProcessResponse(
                    extraction=extraction,
                    agent_reply=agent_reply,
                    audio_base64=self._speak(agent_reply, request),
                    action_taken="SALE_VALIDATION_FAILED",
                )

            return self._handle_record_sale(db, extraction, request)

        # ── Add to catalog ──
        if intent == "add_to_catalog":
            return self._handle_add_to_catalog(db, products, extraction, request, business_type)

        # ── Financial queries (deterministic, no LLM hallucination) ──
        if intent in ["query_pending", "query_daily"]:
            metrics = self._get_summary_metrics(db, merchant_id=merchant.id)
            agent_reply = llm_service.answer_query(request.text, metrics, use_llm=False)
            return VoiceProcessResponse(
                extraction=extraction,
                agent_reply=agent_reply,
                audio_base64=self._speak(agent_reply, request),
                action_taken="QUERY_ANSWERED",
            )

        if intent == "general_qa":
            if extraction.explanation and "catalog me" in (extraction.explanation or "").lower():
                agent_reply = extraction.explanation
            else:
                metrics = self._get_summary_metrics(db, merchant_id=merchant.id)
                agent_reply = llm_service.answer_query(request.text, metrics, use_llm=False)
            return VoiceProcessResponse(
                extraction=extraction,
                agent_reply=agent_reply,
                audio_base64=self._speak(agent_reply, request),
                action_taken="QUERY_ANSWERED",
            )

        agent_reply = extraction.explanation or "Aapka command samajh nahi aaya. Kripya dobara try karein."
        return VoiceProcessResponse(
            extraction=extraction,
            agent_reply=agent_reply,
            audio_base64=self._speak(agent_reply, request),
            action_taken="UNKNOWN_INTENT",
        )

    def _handle_payment_status(
        self, db: Session, merchant_id: int, extraction, request: VoiceProcessRequest
    ) -> VoiceProcessResponse:
        target_sale = None
        if extraction.product_name:
            sales = (
                db.query(Sale)
                .filter(Sale.merchant_id == merchant_id)
                .order_by(Sale.created_at.desc())
                .limit(30)
                .all()
            )
            for s in sales:
                if any(extraction.product_name in it.product_name.lower() for it in s.items):
                    target_sale = s
                    break

            if not target_sale:
                agent_reply = (
                    f"'{extraction.product_name}' ke liye koi recent sale nahi mili. "
                    "Kripya sahi product naam bolein ya pehle sale record karein."
                )
                return VoiceProcessResponse(
                    extraction=extraction,
                    agent_reply=agent_reply,
                    audio_base64=self._speak(agent_reply, request),
                    action_taken="NO_MATCHING_SALE",
                )
        else:
            target_sale = (
                db.query(Sale)
                .filter(Sale.merchant_id == merchant_id)
                .order_by(Sale.created_at.desc())
                .first()
            )

        if target_sale:
            items_str = ", ".join([f"{it.quantity}x {it.product_name}" for it in target_sale.items]) or "Sold item"
            if target_sale.status == "PAID":
                agent_reply = f"Haan. {items_str} ka Rs. {target_sale.total_amount:.2f} payment mil chuka hai. Status: PAID."
            elif target_sale.status == "PARTIAL":
                agent_reply = (
                    f"{items_str} ke liye Rs. {target_sale.received_amount:.2f} receive hua hai, "
                    f"lekin Rs. {target_sale.outstanding_amount:.2f} abhi pending hai. Status: PARTIAL."
                )
            elif target_sale.status == "FAILED":
                agent_reply = f"{items_str} ka payment fail ho gaya hai."
            else:
                agent_reply = (
                    f"Nahi. {items_str} ka Rs. {target_sale.outstanding_amount:.2f} "
                    "payment abhi tak nahi aaya hai."
                )

            return VoiceProcessResponse(
                extraction=extraction,
                agent_reply=agent_reply,
                audio_base64=self._speak(agent_reply, request),
                sale={
                    "id": target_sale.id,
                    "status": target_sale.status,
                    "total_amount": target_sale.total_amount,
                    "received_amount": target_sale.received_amount,
                    "outstanding_amount": target_sale.outstanding_amount,
                    "payment_link_url": target_sale.razorpay_payment_link_url,
                },
                action_taken="PAYMENT_STATUS_CHECKED",
            )

        agent_reply = "Abhi tak koi sale record nahi hui hai."
        return VoiceProcessResponse(
            extraction=extraction,
            agent_reply=agent_reply,
            audio_base64=self._speak(agent_reply, request),
            action_taken="NO_SALES_FOUND",
        )

    def _handle_list_catalog(
        self, products: List[Product], extraction, request: VoiceProcessRequest
    ) -> VoiceProcessResponse:
        if not products:
            agent_reply = (
                "Aapke catalog me abhi koi item nahi hai. "
                "Menu & Items tab se add karein ya bolein: 'Menu mein burger add karo 100 rupaye'."
            )
        else:
            lines = [f"{p.name.title()} — Rs. {p.price:.0f} ({p.category or 'General'})" for p in products[:20]]
            agent_reply = f"Aapke paas {len(products)} items hain: " + "; ".join(lines)
            if len(products) > 20:
                agent_reply += f" ... aur {len(products) - 20} aur items."

        return VoiceProcessResponse(
            extraction=extraction,
            agent_reply=agent_reply,
            audio_base64=self._speak(agent_reply, request),
            sale={"catalog_count": len(products)},
            action_taken="CATALOG_LISTED",
        )

    def _handle_search_catalog(
        self, products: List[Product], extraction, request: VoiceProcessRequest
    ) -> VoiceProcessResponse:
        query = (extraction.product_name or "").lower()
        matches = [p for p in products if query and (query in p.name or p.name in query)]

        if not matches and query:
            matches = [p for p in products if any(w in p.name for w in query.split())]

        if matches:
            p = matches[0]
            attrs = {}
            try:
                attrs = json.loads(p.attributes or "{}")
            except Exception:
                pass
            attr_str = ", ".join(f"{k}: {v}" for k, v in attrs.items()) if attrs else ""
            agent_reply = (
                f"{p.name.title()} — Rs. {p.price:.2f}, category: {p.category or 'General'}"
                + (f", {attr_str}" if attr_str else "")
                + (f", unit: {p.unit}" if p.unit else "")
            )
            return VoiceProcessResponse(
                extraction=extraction,
                agent_reply=agent_reply,
                audio_base64=self._speak(agent_reply, request),
                sale={"product": {"id": p.id, "name": p.name, "price": p.price, "category": p.category}},
                action_taken="CATALOG_SEARCHED",
            )

        agent_reply = f"'{query or 'item'}' catalog me nahi mila. Naya item add karne ke liye bolein: 'Menu mein add karo'."
        return VoiceProcessResponse(
            extraction=extraction,
            agent_reply=agent_reply,
            audio_base64=self._speak(agent_reply, request),
            action_taken="CATALOG_SEARCH_NOT_FOUND",
        )

    def _handle_record_sale(self, db: Session, extraction, request: VoiceProcessRequest) -> VoiceProcessResponse:
        sale_items = [
            SaleItemCreate(
                product_name=item.product_name,
                quantity=item.quantity,
                unit_price=item.unit_price,
            )
            for item in extraction.items
        ]
        sale_in = SaleCreate(
            items=sale_items,
            customer_name=extraction.customer_name or "Store Customer",
            raw_voice_transcript=request.text,
            auto_create_payment_link=True,
        )

        try:
            sale = sales_service.create_sale(db, sale_in)
        except ValueError as exc:
            agent_reply = str(exc)
            return VoiceProcessResponse(
                extraction=extraction,
                agent_reply=agent_reply,
                audio_base64=self._speak(agent_reply, request),
                action_taken="SALE_VALIDATION_FAILED",
            )

        items_str = ", ".join([f"{it.quantity}x {it.product_name}" for it in sale.items])
        link_note = f"Razorpay Payment Link ready: {sale.razorpay_payment_link_url}" if sale.razorpay_payment_link_url else ""
        agent_reply = f"Rs. {sale.total_amount:.2f} ka sale record ho gaya ({items_str}). {link_note}"
        spoken_text = f"Rs. {sale.total_amount:.0f} ka sale record ho gaya. {items_str}."

        return VoiceProcessResponse(
            extraction=extraction,
            agent_reply=agent_reply,
            audio_base64=self._speak(spoken_text, request),
            sale={
                "id": sale.id,
                "items": items_str,
                "total_amount": sale.total_amount,
                "received_amount": sale.received_amount,
                "outstanding_amount": sale.outstanding_amount,
                "status": sale.status,
                "payment_link_url": sale.razorpay_payment_link_url,
            },
            action_taken="SALE_CREATED",
        )

    def _handle_add_to_catalog(
        self,
        db: Session,
        products: List[Product],
        extraction,
        request: VoiceProcessRequest,
        business_type: Optional[str],
    ) -> VoiceProcessResponse:
        preset = get_business_preset(business_type)
        default_category = preset.get("default_categories", ["General"])[0]

        added_products = []
        items_to_add = extraction.items if extraction.items else []
        if not items_to_add and extraction.product_name:
            items_to_add = [VoiceItemExtracted(product_name=extraction.product_name, unit_price=0.0)]

        if items_to_add:
            for it in items_to_add:
                prod = sales_service.add_or_update_product(
                    db=db,
                    name=it.product_name,
                    price=it.unit_price or 0.0,
                    category=it.category or default_category,
                    unit=it.unit,
                )
                added_products.append(prod)

            summary_str = ", ".join([f"{p.name.title()} (Rs. {p.price:.2f})" for p in added_products])
            agent_reply = f"Naya item {summary_str} aapke catalog me successfully add kar diya gaya hai."
            spoken_text = f"{summary_str} catalog me add ho gaya hai."

            return VoiceProcessResponse(
                extraction=extraction,
                agent_reply=agent_reply,
                audio_base64=self._speak(spoken_text, request),
                sale={
                    "catalog_items": [
                        {"id": p.id, "name": p.name, "price": p.price, "category": p.category}
                        for p in added_products
                    ]
                },
                action_taken="CATALOG_ITEM_ADDED",
            )

        agent_reply = "Item ka naam samajh nahi aaya. Kripya bolein: 'Menu mein burger add karo 100 rupaye'."
        return VoiceProcessResponse(
            extraction=extraction,
            agent_reply=agent_reply,
            audio_base64=self._speak(agent_reply, request),
            action_taken="CATALOG_ADD_FAILED",
        )

    def _get_summary_metrics(self, db: Session, merchant_id: Optional[int] = None) -> Dict[str, Any]:
        today_start = datetime.combine(date.today(), datetime.min.time())
        query = db.query(Sale)
        if merchant_id:
            query = query.filter(Sale.merchant_id == merchant_id)

        all_sales = query.all()
        today_sales = sum(s.total_amount for s in all_sales if s.created_at >= today_start)
        total_collected = sum(s.received_amount for s in all_sales)
        total_outstanding = sum(s.outstanding_amount for s in all_sales)

        paid_count = sum(1 for s in all_sales if s.status == "PAID")
        partial_count = sum(1 for s in all_sales if s.status == "PARTIAL")
        pending_count = sum(1 for s in all_sales if s.status == "PENDING")

        return {
            "today_sales": today_sales,
            "total_collected": total_collected,
            "total_outstanding": total_outstanding,
            "total_transactions": len(all_sales),
            "paid_count": paid_count,
            "partial_count": partial_count,
            "pending_count": pending_count,
        }


merchant_agent = MerchantAgent()
