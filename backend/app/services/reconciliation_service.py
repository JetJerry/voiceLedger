from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from backend.app.models import Sale, Payment, WebhookEvent


class ReconciliationService:
    def process_payment_event(
        self,
        db: Session,
        razorpay_payment_id: str,
        amount_in_inr: float,
        status: str,
        sale_id: Optional[str] = None,
        payment_link_id: Optional[str] = None,
        order_id: Optional[str] = None,
        method: Optional[str] = None,
        vpa: Optional[str] = None,
        email: Optional[str] = None,
        contact: Optional[str] = None,
        error_code: Optional[str] = None,
        error_description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Deterministically processes a payment event and reconciles receivable state.
        """
        # 1. Idempotency Check
        existing_payment = db.query(Payment).filter(
            Payment.razorpay_payment_id == razorpay_payment_id
        ).first()

        if existing_payment:
            # Already processed this payment
            sale = existing_payment.sale
            return {
                "result": "ALREADY_PROCESSED",
                "payment_id": razorpay_payment_id,
                "sale_id": sale.id if sale else None,
                "sale_status": sale.status if sale else "UNMATCHED",
                "expected": sale.total_amount if sale else None,
                "received": sale.received_amount if sale else amount_in_inr,
                "outstanding": sale.outstanding_amount if sale else 0.0
            }

        # 2. Find matching Sale
        target_sale: Optional[Sale] = None
        if sale_id:
            target_sale = db.query(Sale).filter(Sale.id == sale_id).first()
            
        if not target_sale and payment_link_id:
            target_sale = db.query(Sale).filter(
                Sale.razorpay_payment_link_id == payment_link_id
            ).first()

        # 3. Create Payment record
        payment = Payment(
            sale_id=target_sale.id if target_sale else None,
            razorpay_payment_id=razorpay_payment_id,
            razorpay_order_id=order_id,
            razorpay_payment_link_id=payment_link_id,
            amount=amount_in_inr,
            currency="INR",
            status=status,
            method=method,
            vpa=vpa,
            email=email,
            contact=contact,
            error_code=error_code,
            error_description=error_description
        )
        db.add(payment)
        db.flush()

        # 4. If No Sale Matched -> UNMATCHED
        if not target_sale:
            db.commit()
            return {
                "result": "UNMATCHED",
                "payment_id": razorpay_payment_id,
                "amount": amount_in_inr,
                "status": "UNMATCHED",
                "message": "Payment received without matching local sale record."
            }

        # 5. Reconcile matched Sale
        if status in ["captured", "paid", "authorized"]:
            # Sum all successful captured payments for this sale
            all_payments = db.query(Payment).filter(
                Payment.sale_id == target_sale.id,
                Payment.status.in_(["captured", "paid", "authorized"])
            ).all()
            
            cumulative_received = sum(p.amount for p in all_payments)
            target_sale.received_amount = cumulative_received
            target_sale.outstanding_amount = max(0.0, target_sale.total_amount - cumulative_received)

            if cumulative_received >= target_sale.total_amount:
                target_sale.status = "PAID"
                target_sale.outstanding_amount = 0.0
            elif cumulative_received > 0:
                target_sale.status = "PARTIAL"
            else:
                target_sale.status = "PENDING"
                
        elif status == "failed":
            if target_sale.received_amount == 0:
                target_sale.status = "FAILED"

        # 6. Trigger Live Voice Soundbox Announcement
        try:
            from backend.app.services.payment_announcement_service import payment_announcement_service
            items_data = [{"product_name": it.product_name, "quantity": it.quantity} for it in target_sale.items]
            payment_announcement_service.create_announcement(
                sale_id=target_sale.id,
                merchant_id=target_sale.merchant_id,
                amount=amount_in_inr,
                status=target_sale.status,
                customer_name=target_sale.customer_name,
                items=items_data
            )
        except Exception as e:
            pass

        # 7. Persist deterministic reconciliation state to database
        db.commit()
        db.refresh(target_sale)

        return {
            "result": "MATCHED",
            "sale_id": target_sale.id,
            "customer_name": target_sale.customer_name,
            "sale_status": target_sale.status,
            "expected": target_sale.total_amount,
            "received": target_sale.received_amount,
            "outstanding": target_sale.outstanding_amount,
            "payment_id": razorpay_payment_id
        }

    def reconcile_from_webhook_payload(self, db: Session, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parses standard Razorpay webhook payloads and executes reconciliation.
        Supports payment_link.paid, payment.captured, payment.failed, etc.
        """
        event_type = payload.get("event", "")
        payload_data = payload.get("payload", {})
        
        payment_entity = payload_data.get("payment", {}).get("entity", {})
        payment_link_entity = payload_data.get("payment_link", {}).get("entity", {})
        
        # Extract attributes
        razorpay_payment_id = payment_entity.get("id") or f"pay_wh_{payload.get('created_at', '')}"
        amount_paise = payment_entity.get("amount") or payment_link_entity.get("amount_paid") or 0
        amount_inr = float(amount_paise) / 100.0
        
        status = payment_entity.get("status")
        if not status:
            status = "captured" if "paid" in event_type else "failed"

        # Sale ID from notes
        sale_id = None
        notes = payment_entity.get("notes") or payment_link_entity.get("notes") or {}
        if isinstance(notes, dict):
            sale_id = notes.get("sale_id")
            
        payment_link_id = payment_link_entity.get("id") or payment_entity.get("payment_link_id")
        order_id = payment_entity.get("order_id")
        method = payment_entity.get("method")
        vpa = payment_entity.get("vpa")
        email = payment_entity.get("email")
        contact = payment_entity.get("contact")
        error_code = payment_entity.get("error_code")
        error_description = payment_entity.get("error_description")

        return self.process_payment_event(
            db=db,
            razorpay_payment_id=razorpay_payment_id,
            amount_in_inr=amount_inr,
            status=status,
            sale_id=sale_id,
            payment_link_id=payment_link_id,
            order_id=order_id,
            method=method,
            vpa=vpa,
            email=email,
            contact=contact,
            error_code=error_code,
            error_description=error_description
        )


reconciliation_service = ReconciliationService()
