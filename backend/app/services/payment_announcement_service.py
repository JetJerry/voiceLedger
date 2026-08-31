import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from backend.app.services.tts_service import tts_service

logger = logging.getLogger("voiceledger.payment_announcement")


class PaymentAnnouncementService:
    def __init__(self):
        # In-memory queue: { announcement_id: announcement_data }
        self._announcements: Dict[str, Dict[str, Any]] = {}

    def create_announcement(
        self,
        sale_id: str,
        merchant_id: int,
        amount: float,
        status: str,
        customer_name: Optional[str] = None,
        items: Optional[List[Dict[str, Any]]] = None,
        lang: str = "hi"
    ) -> Dict[str, Any]:
        """
        Creates a voice payment announcement with high-speed Neural TTS synthesis.
        Like a Paytm / PhonePe Soundbox speaker!
        """
        items_list = items or []
        if items_list:
            items_parts = [f"{it.get('quantity', 1)} {it.get('product_name', 'item')}" for it in items_list]
            if len(items_parts) == 1:
                items_str = items_parts[0]
            elif len(items_parts) == 2:
                items_str = f"{items_parts[0]} aur {items_parts[1]}"
            else:
                items_str = f"{', '.join(items_parts[:-1])} aur {items_parts[-1]}"
        else:
            items_str = "order"

        customer_str = f"{customer_name} se " if customer_name and customer_name.strip() and customer_name.lower() != "walk-in customer" else ""

        # Construct natural Hindi speech announcement
        if status.lower() in ["captured", "paid", "authorized"]:
            speech_text = (
                f"Payment receive ho gaya! {customer_str}{items_str} ka "
                f"{int(amount) if amount.is_integer() else amount:.2f} rupaye payment successfully receive ho chuka hai."
            )
            title = "Payment Received"
        elif status.lower() == "partial":
            speech_text = (
                f"{customer_str}{items_str} ke liye "
                f"{int(amount) if amount.is_integer() else amount:.2f} rupaye receive hue hain. Pending balance baaki hai."
            )
            title = "Partial Payment Received"
        else:
            speech_text = f"{customer_str}{items_str} ka payment fail ho gaya hai."
            title = "Payment Failed"

        announcement_id = f"ann_{uuid.uuid4().hex[:10]}"
        
        # Generate high-performance Neural TTS base64 audio
        audio_base64 = ""
        try:
            audio_base64 = tts_service.generate_speech_base64(speech_text, lang=lang)
        except Exception as e:
            logger.warning("Could not pre-synthesize TTS audio for announcement: %s", e)

        announcement = {
            "id": announcement_id,
            "sale_id": sale_id,
            "merchant_id": merchant_id,
            "amount": amount,
            "status": status.upper(),
            "customer_name": customer_name,
            "items_summary": items_str,
            "title": title,
            "speech_text": speech_text,
            "audio_base64": audio_base64,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "acknowledged": False,
        }

        self._announcements[announcement_id] = announcement
        logger.info("[PaymentAnnouncement] Created soundbox announcement: %s", speech_text)
        return announcement

    def get_unannounced_for_merchant(self, merchant_id: int) -> List[Dict[str, Any]]:
        """
        Returns all unacknowledged payment announcements for a given merchant.
        """
        results = [
            ann for ann in self._announcements.values()
            if ann["merchant_id"] == merchant_id and not ann["acknowledged"]
        ]
        # Return sorted by timestamp
        return sorted(results, key=lambda x: x["created_at"])

    def acknowledge_announcement(self, announcement_id: str) -> bool:
        """
        Marks an announcement as acknowledged by the frontend speaker.
        """
        if announcement_id in self._announcements:
            self._announcements[announcement_id]["acknowledged"] = True
            return True
        return False


payment_announcement_service = PaymentAnnouncementService()
