from datetime import datetime, timezone, date
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from backend.app.models import Product, Sale, Payment
from backend.app.schemas.voice import VoiceProcessRequest, VoiceProcessResponse
from backend.app.schemas.sale import SaleCreate, SaleItemCreate
from backend.app.services.llm_service import llm_service
from backend.app.services.sales_service import sales_service
from backend.app.services.recovery_service import recovery_service
from backend.app.services.tts_service import tts_service


class MerchantAgent:
    def process_merchant_command(self, db: Session, request: VoiceProcessRequest) -> VoiceProcessResponse:
        """
        Guarded Agent Orchestrator:
        - Dynamically passes active merchant database catalog items to LLMService.
        - Handles sale recording and payment arrival verification via voice.
        - Generates natural Hindi/English neural TTS speech audio.
        """
        # Active merchant context
        merchant = sales_service.get_or_create_merchant(db)

        # Fetch active merchant catalog products
        products = db.query(Product).filter(Product.merchant_id == merchant.id, Product.is_active == True).all()
        catalog_names = [p.name for p in products]

        # 1. AI Extraction
        extraction = llm_service.extract_transaction(request.text, catalog_items=catalog_names)
        intent = extraction.intent

        # 2. Handle Intent: Check whether payment of the sold product has arrived or not
        if intent == "check_payment_status":
            target_sale = None
            if extraction.product_name:
                # Find recent sale matching the spoken product name for this merchant
                sales = db.query(Sale).filter(Sale.merchant_id == merchant.id).order_by(Sale.created_at.desc()).limit(20).all()
                for s in sales:
                    if any(extraction.product_name in it.product_name.lower() for it in s.items):
                        target_sale = s
                        break

            # Fallback to the latest recorded sale for this merchant
            if not target_sale:
                target_sale = db.query(Sale).filter(Sale.merchant_id == merchant.id).order_by(Sale.created_at.desc()).first()

            if target_sale:
                items_str = ", ".join([f"{it.quantity}x {it.product_name}" for it in target_sale.items]) or "Sold item"
                if target_sale.status == "PAID":
                    agent_reply = f"Haan! {items_str} ka Rs. {target_sale.total_amount:.2f} payment receive ho chuka hai (PAID ✅)."
                elif target_sale.status == "PARTIAL":
                    agent_reply = f"{items_str} ke liye Rs. {target_sale.received_amount:.2f} receive hua hai, lekin Rs. {target_sale.outstanding_amount:.2f} abhi pending hai (PARTIAL ⚠️)."
                elif target_sale.status == "FAILED":
                    agent_reply = f"{items_str} ka payment fail ho gaya hai (FAILED ❌)."
                else:
                    agent_reply = f"Nahi, {items_str} ka Rs. {target_sale.outstanding_amount:.2f} payment abhi tak nahi aaya hai (PENDING ⏳)."

                # Generate TTS voice audio
                audio_base64 = tts_service.generate_speech_base64(agent_reply, lang=request.voice_lang) if request.speak_response else None

                return VoiceProcessResponse(
                    extraction=extraction,
                    agent_reply=agent_reply,
                    audio_base64=audio_base64,
                    sale={
                        "id": target_sale.id,
                        "status": target_sale.status,
                        "total_amount": target_sale.total_amount,
                        "received_amount": target_sale.received_amount,
                        "outstanding_amount": target_sale.outstanding_amount,
                        "payment_link_url": target_sale.razorpay_payment_link_url
                    },
                    action_taken="PAYMENT_STATUS_CHECKED"
                )
            else:
                agent_reply = "Abhi tak koi sale record nahi hui hai."
                audio_base64 = tts_service.generate_speech_base64(agent_reply, lang=request.voice_lang) if request.speak_response else None
                return VoiceProcessResponse(
                    extraction=extraction,
                    agent_reply=agent_reply,
                    audio_base64=audio_base64,
                    action_taken="NO_SALES_FOUND"
                )

        # 3. Handle Intent: Record a new product sale
        elif intent == "record_sale" and extraction.items:
            sale_items = [
                SaleItemCreate(
                    product_name=item.product_name,
                    quantity=item.quantity,
                    unit_price=item.unit_price
                )
                for item in extraction.items
            ]
            sale_in = SaleCreate(
                items=sale_items,
                customer_name=extraction.customer_name or "Store Customer",
                raw_voice_transcript=request.text,
                auto_create_payment_link=True
            )
            sale = sales_service.create_sale(db, sale_in)

            items_str = ", ".join([f"{it.quantity}x {it.product_name}" for it in sale.items])
            link_note = f"Razorpay Payment Link ready: {sale.razorpay_payment_link_url}" if sale.razorpay_payment_link_url else ""
            agent_reply = f"Rs. {sale.total_amount:.2f} ka sale record ho gaya ({items_str}). {link_note}"
            
            # Generate TTS voice audio
            spoken_text = f"Rs. {sale.total_amount:.0f} ka sale record ho gaya. {items_str}."
            audio_base64 = tts_service.generate_speech_base64(spoken_text, lang=request.voice_lang) if request.speak_response else None

            return VoiceProcessResponse(
                extraction=extraction,
                agent_reply=agent_reply,
                audio_base64=audio_base64,
                sale={
                    "id": sale.id,
                    "items": items_str,
                    "total_amount": sale.total_amount,
                    "received_amount": sale.received_amount,
                    "outstanding_amount": sale.outstanding_amount,
                    "status": sale.status,
                    "payment_link_url": sale.razorpay_payment_link_url
                },
                action_taken="SALE_CREATED"
            )

        # 4. Handle Intent: Add new item(s) to catalog / menu via voice
        elif intent == "add_to_catalog":
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
                        category=it.category or "General"
                    )
                    added_products.append(prod)

                summary_str = ", ".join([f"{p.name.title()} (Rs. {p.price:.2f})" for p in added_products])
                agent_reply = f"Naya item {summary_str} aapke catalog me add ho gaya hai! ✅"
                spoken_text = f"{summary_str} catalog me add ho gaya hai."
                audio_base64 = tts_service.generate_speech_base64(spoken_text, lang=request.voice_lang) if request.speak_response else None

                return VoiceProcessResponse(
                    extraction=extraction,
                    agent_reply=agent_reply,
                    audio_base64=audio_base64,
                    sale={
                        "catalog_items": [
                            {"id": p.id, "name": p.name, "price": p.price, "category": p.category}
                            for p in added_products
                        ]
                    },
                    action_taken="CATALOG_ITEM_ADDED"
                )
            else:
                agent_reply = "Item ka naam samajh nahi aaya. Kripya bolein: 'Menu mein burger add karo 100 rupaye'."
                audio_base64 = tts_service.generate_speech_base64(agent_reply, lang=request.voice_lang) if request.speak_response else None
                return VoiceProcessResponse(
                    extraction=extraction,
                    agent_reply=agent_reply,
                    audio_base64=audio_base64,
                    action_taken="CATALOG_ADD_FAILED"
                )

        # 5. Handle Intent: Query Pending / Collection Summaries
        elif intent in ["query_pending", "query_daily", "general_qa"]:
            metrics = self._get_summary_metrics(db, merchant_id=merchant.id)
            agent_reply = llm_service.answer_query(request.text, metrics)
            audio_base64 = tts_service.generate_speech_base64(agent_reply, lang=request.voice_lang) if request.speak_response else None
            return VoiceProcessResponse(
                extraction=extraction,
                agent_reply=agent_reply,
                audio_base64=audio_base64,
                action_taken="QUERY_ANSWERED"
            )

        # Default fallback
        agent_reply = extraction.explanation or "Aapka command samajh nahi aaya. Kripya dobara try karein."
        audio_base64 = tts_service.generate_speech_base64(agent_reply, lang=request.voice_lang) if request.speak_response else None
        return VoiceProcessResponse(
            extraction=extraction,
            agent_reply=agent_reply,
            audio_base64=audio_base64,
            action_taken="UNKNOWN_INTENT"
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
            "pending_count": pending_count
        }


merchant_agent = MerchantAgent()
