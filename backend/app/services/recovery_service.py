from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from backend.app.models import Sale, RecoveryAction, Customer
from backend.app.schemas.recovery import RecoveryPriorityItem
from backend.app.services.razorpay_service import razorpay_service


class RecoveryService:
    def get_recovery_queue(self, db: Session, merchant_id: int = 1) -> List[RecoveryPriorityItem]:
        """
        Retrieves all unpaid / partially paid sales and ranks them by recovery priority score.
        """
        pending_sales = db.query(Sale).filter(
            Sale.merchant_id == merchant_id,
            Sale.outstanding_amount > 0,
            Sale.status.in_(["PENDING", "PARTIAL"])
        ).all()

        queue: List[RecoveryPriorityItem] = []
        now = datetime.now(timezone.utc)

        for s in pending_sales:
            # Handle timezone naive/aware comparison
            created_at = s.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
                
            age_seconds = (now - created_at).total_seconds()
            days_overdue = max(0, int(age_seconds // 86400))
            hours_overdue = max(0, int(age_seconds // 3600))

            # Priority formula: amount * overdue factor
            overdue_factor = 1.0 + (0.5 * min(days_overdue, 7))
            priority_score = s.outstanding_amount * overdue_factor

            if priority_score >= 800 or days_overdue >= 2:
                level = "HIGH"
            elif priority_score >= 250 or hours_overdue >= 6:
                level = "MEDIUM"
            else:
                level = "LOW"

            rec_action = (
                f"Resend Payment Link for ₹{s.outstanding_amount:.2f} via WhatsApp"
                if s.status == "PARTIAL"
                else f"Follow up on pending ₹{s.outstanding_amount:.2f} bill"
            )

            queue.append(
                RecoveryPriorityItem(
                    sale_id=s.id,
                    customer_name=s.customer_name,
                    customer_phone=s.customer.phone if s.customer else None,
                    expected_amount=s.total_amount,
                    received_amount=s.received_amount,
                    outstanding_amount=s.outstanding_amount,
                    days_overdue=days_overdue,
                    priority_score=round(priority_score, 2),
                    priority_level=level,
                    recommended_action=rec_action,
                    payment_link_url=s.razorpay_payment_link_url,
                    created_at=s.created_at
                )
            )

        # Sort descending by priority score
        queue.sort(key=lambda x: x.priority_score, reverse=True)
        return queue

    def trigger_recovery_action(
        self,
        db: Session,
        sale_id: str,
        action_type: str = "payment_link_resend",
        channel: str = "whatsapp",
        custom_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Triggers a recovery action, constructs payment message, and logs recovery history.
        """
        sale = db.query(Sale).filter(Sale.id == sale_id).first()
        if not sale:
            raise ValueError(f"Sale #{sale_id} not found")

        # Refresh or ensure payment link exists
        if not sale.razorpay_payment_link_url:
            link_info = razorpay_service.create_payment_link(
                amount=sale.outstanding_amount,
                sale_id=sale.id,
                customer_name=sale.customer_name,
                customer_phone=sale.customer.phone if sale.customer else None,
                description=f"Outstanding balance recovery for #{sale.id}"
            )
            sale.razorpay_payment_link_id = link_info.get("id")
            sale.razorpay_payment_link_url = link_info.get("short_url")

        # Compose WhatsApp reminder text
        phone = sale.customer.phone if sale.customer else ""
        link = sale.razorpay_payment_link_url or "https://rzp.io"
        
        default_msg = (
            f"Namaste {sale.customer_name}, aapka ₹{sale.outstanding_amount:.2f} ka payment "
            f"VoiceLedger Merchant par baaki hai. Kripya is link se pay karein: {link} . Dhanyawaad!"
        )
        final_message = custom_message or default_msg

        # Record action in DB
        action = RecoveryAction(
            sale_id=sale.id,
            action_type=action_type,
            status="SENT",
            channel=channel,
            notes=final_message
        )
        db.add(action)
        db.commit()
        db.refresh(action)

        # Generate WhatsApp click-to-chat URL
        phone_digits = "".join(filter(str.isdigit, phone or ""))
        import urllib.parse
        encoded_text = urllib.parse.quote(final_message)
        wa_url = f"https://wa.me/{phone_digits}?text={encoded_text}" if phone_digits else None

        return {
            "id": action.id,
            "sale_id": sale.id,
            "customer_name": sale.customer_name,
            "outstanding_amount": sale.outstanding_amount,
            "payment_link_url": sale.razorpay_payment_link_url,
            "action_type": action.action_type,
            "status": action.status,
            "channel": action.channel,
            "message": final_message,
            "whatsapp_url": wa_url,
            "created_at": action.created_at
        }


recovery_service = RecoveryService()
