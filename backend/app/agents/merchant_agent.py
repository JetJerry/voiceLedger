from datetime import datetime, timezone, date
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.models import Merchant, Customer, Product, Sale, Payment
from backend.app.schemas.voice import VoiceProcessRequest, VoiceProcessResponse, VoiceItemExtracted
from backend.app.schemas.sale import SaleCreate, SaleItemCreate
from backend.app.services.llm_service import llm_service
from backend.app.services.sales_service import sales_service
from backend.app.services.recovery_service import recovery_service


class MerchantAgent:
    def process_merchant_command(self, db: Session, request: VoiceProcessRequest) -> VoiceProcessResponse:
        """
        Guarded Agent Orchestrator:
        1. Fetches current catalog names for extraction grounding.
        2. Uses LLMService to parse spoken/typed command.
        3. Routes to deterministic backend tools.
        4. Returns verified state and natural Hinglish explanation.
        """
        # Get catalog items for context
        products = db.query(Product).all()
        catalog_names = [p.name for p in products]

        # 1. AI Extraction
        extraction = llm_service.extract_transaction(request.text, catalog_items=catalog_names)
        intent = extraction.intent
        
        # 2. Guarded Tool Dispatch
        if intent == "record_sale" and extraction.items:
            # Tool: Create Sale & Payment Link
            sale_items = [
                SaleItemCreate(
                    product_name=item.product_name,
                    quantity=item.quantity,
                    unit_price=item.unit_price
                )
                for item in extraction.items
            ]
            sale_in = SaleCreate(
                customer_name=extraction.customer_name or "Walk-in Customer",
                customer_phone=extraction.customer_phone,
                items=sale_items,
                raw_voice_transcript=request.text,
                auto_create_payment_link=True
            )
            sale = sales_service.create_sale(db, sale_in)

            items_str = ", ".join([f"{it.quantity}x {it.product_name}" for it in sale.items])
            link_note = f"Razorpay Payment Link ready: {sale.razorpay_payment_link_url}" if sale.razorpay_payment_link_url else ""
            agent_reply = f"₹{sale.total_amount:.2f} ka sale record ho gaya ({items_str}) for {sale.customer_name}. {link_note}"

            return VoiceProcessResponse(
                extraction=extraction,
                agent_reply=agent_reply,
                sale={
                    "id": sale.id,
                    "customer_name": sale.customer_name,
                    "total_amount": sale.total_amount,
                    "received_amount": sale.received_amount,
                    "outstanding_amount": sale.outstanding_amount,
                    "status": sale.status,
                    "payment_link_url": sale.razorpay_payment_link_url
                },
                action_taken="SALE_CREATED"
            )

        elif intent in ["query_pending", "query_daily", "general_qa"]:
            # Tool: Query Financial Metrics
            metrics = self._get_summary_metrics(db)
            agent_reply = llm_service.answer_query(request.text, metrics)
            return VoiceProcessResponse(
                extraction=extraction,
                agent_reply=agent_reply,
                action_taken="QUERY_ANSWERED"
            )

        elif intent == "query_status":
            # Tool: Query Customer Payment Status
            cust_name = extraction.customer_name
            if cust_name:
                sale = db.query(Sale).filter(Sale.customer_name.ilike(f"%{cust_name}%")).order_by(Sale.created_at.desc()).first()
                if sale:
                    if sale.status == "PAID":
                        agent_reply = f"{sale.customer_name} ka ₹{sale.total_amount:.2f} payment receive ho chuka hai (PAID ✅)."
                    elif sale.status == "PARTIAL":
                        agent_reply = f"{sale.customer_name} ne ₹{sale.received_amount:.2f} pay kiya hai, lekin ₹{sale.outstanding_amount:.2f} abhi pending hai (PARTIAL ⚠️)."
                    else:
                        agent_reply = f"{sale.customer_name} ka ₹{sale.outstanding_amount:.2f} payment abhi pending hai."
                    return VoiceProcessResponse(
                        extraction=extraction,
                        agent_reply=agent_reply,
                        sale={"id": sale.id, "customer_name": sale.customer_name, "status": sale.status, "outstanding": sale.outstanding_amount},
                        action_taken="STATUS_CHECKED"
                    )
            
            agent_reply = "Aapka customer record nahi mila. Kripya customer ka naam specify karein."
            return VoiceProcessResponse(
                extraction=extraction,
                agent_reply=agent_reply,
                action_taken="NO_CUSTOMER_FOUND"
            )

        elif intent == "trigger_recovery":
            # Tool: Trigger Payment Link Recovery
            cust_name = extraction.customer_name
            sale = None
            if cust_name:
                sale = db.query(Sale).filter(
                    Sale.customer_name.ilike(f"%{cust_name}%"),
                    Sale.outstanding_amount > 0
                ).order_by(Sale.created_at.desc()).first()

            if not sale:
                # Get the highest priority pending sale
                queue = recovery_service.get_recovery_queue(db)
                if queue:
                    sale = db.query(Sale).filter(Sale.id == queue[0].sale_id).first()

            if sale:
                action_result = recovery_service.trigger_recovery_action(db, sale_id=sale.id)
                agent_reply = f"{sale.customer_name} ko ₹{sale.outstanding_amount:.2f} ke liye recovery reminder WhatsApp par bhej diya gaya hai."
                return VoiceProcessResponse(
                    extraction=extraction,
                    agent_reply=agent_reply,
                    sale={"id": sale.id, "customer_name": sale.customer_name, "outstanding": sale.outstanding_amount},
                    action_taken="RECOVERY_TRIGGERED"
                )
            else:
                agent_reply = "Filhaal koi outstanding payment pending nahi hai jiske liye reminder bheja jaye."
                return VoiceProcessResponse(
                    extraction=extraction,
                    agent_reply=agent_reply,
                    action_taken="NO_PENDING_PAYMENTS"
                )

        # Default fallback
        agent_reply = extraction.explanation or "Aapka command samajh nahi aaya. Kripya dobara try karein."
        return VoiceProcessResponse(
            extraction=extraction,
            agent_reply=agent_reply,
            action_taken="UNKNOWN_INTENT"
        )

    def _get_summary_metrics(self, db: Session) -> Dict[str, Any]:
        today_start = datetime.combine(date.today(), datetime.min.time())
        
        sales_today = db.query(Sale).filter(Sale.created_at >= today_start).all()
        today_sales = sum(s.total_amount for s in sales_today)
        
        all_sales = db.query(Sale).all()
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
