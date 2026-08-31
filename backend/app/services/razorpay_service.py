import hashlib
import hmac
import json
import logging
import uuid
from typing import Any, Dict, Optional

import httpx

from backend.app.config import settings

logger = logging.getLogger("voiceledger.razorpay")


class RazorpayService:
    BASE_URL = "https://api.razorpay.com/v1"

    def __init__(self):
        self._key_id: Optional[str] = None
        self._key_secret: Optional[str] = None
        self._webhook_secret: Optional[str] = None

    @property
    def key_id(self) -> str:
        return self._key_id if self._key_id is not None else settings.RAZORPAY_KEY_ID

    @key_id.setter
    def key_id(self, val: str):
        self._key_id = val

    @property
    def key_secret(self) -> str:
        return self._key_secret if self._key_secret is not None else settings.RAZORPAY_KEY_SECRET

    @key_secret.setter
    def key_secret(self, val: str):
        self._key_secret = val

    @property
    def webhook_secret(self) -> str:
        return self._webhook_secret if self._webhook_secret is not None else settings.RAZORPAY_WEBHOOK_SECRET

    @webhook_secret.setter
    def webhook_secret(self, val: str):
        self._webhook_secret = val

    @property
    def is_configured(self) -> bool:
        return bool(self.key_id and self.key_secret and not self.key_id.startswith("rzp_test_YOUR"))

    def create_payment_link(
        self,
        amount: float,
        sale_id: str,
        customer_name: Optional[str] = None,
        customer_phone: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates a Razorpay Test Mode Payment Link.
        Converts INR to paise (e.g. ₹200.00 -> 20000 paise).
        """
        amount_in_paise = int(round(amount * 100))
        if amount_in_paise <= 0:
            raise ValueError("Amount must be greater than 0")

        # Format customer payload with valid non-repeating contact number
        customer_payload = {
            "name": customer_name or "Valued Customer"
        }
        if customer_phone:
            digits = "".join(filter(str.isdigit, str(customer_phone)))
            if len(digits) == 10:
                customer_payload["contact"] = f"+91{digits}"
            elif len(digits) > 10:
                customer_payload["contact"] = f"+{digits}"
            else:
                customer_payload["contact"] = "+919876543210"
        else:
            customer_payload["contact"] = "+919876543210"

        # 1. Live Razorpay Test Mode Call if keys are configured
        if self.is_configured:
            try:
                payload = {
                    "amount": amount_in_paise,
                    "currency": "INR",
                    "accept_partial": True,
                    "first_min_partial_amount": 100,
                    "description": description or f"Payment for Sale #{sale_id}",
                    "customer": customer_payload,
                    "notify": {
                        "sms": False,
                        "email": False
                    },
                    "reminder_enable": True,
                    "notes": {
                        "sale_id": str(sale_id),
                        "merchant_name": settings.DEFAULT_MERCHANT_NAME
                    }
                }
                
                with httpx.Client(auth=(self.key_id, self.key_secret), timeout=10.0) as client:
                    response = client.post(f"{self.BASE_URL}/payment_links", json=payload)
                    
                if response.status_code in [200, 201]:
                    data = response.json()
                    return {
                        "id": data.get("id"),
                        "short_url": data.get("short_url"),
                        "amount": amount,
                        "currency": "INR",
                        "status": data.get("status", "created"),
                        "sale_id": sale_id,
                        "is_live_api": True
                    }
                else:
                    print(f"Razorpay API Error ({response.status_code}): {response.text}")
            except Exception as e:
                print(f"Razorpay connection error: {e}")

        # 2. Test Mode Sandbox Simulation (Deterministic Test Link for zero-key local demo)
        sim_id = f"plink_{uuid.uuid4().hex[:14]}"
        sim_url = f"https://rzp.io/i/{sim_id[:8]}"
        return {
            "id": sim_id,
            "short_url": sim_url,
            "amount": amount,
            "currency": "INR",
            "status": "created",
            "sale_id": sale_id,
            "is_live_api": False
        }

    def verify_webhook_signature(self, raw_body: bytes, signature: str) -> bool:
        """
        Verifies Razorpay Webhook HMAC SHA256 signature.
        """
        if not raw_body:
            logger.warning("Razorpay webhook payload was empty")
            return False

        if not self.webhook_secret:
            if settings.DEBUG:
                logger.warning("Razorpay webhook secret unset; allowing request in debug mode only")
                return True
            logger.error("Razorpay webhook secret is missing")
            return False

        if not signature:
            logger.warning("Missing Razorpay signature header")
            return False

        try:
            expected_signature = hmac.new(
                key=self.webhook_secret.encode("utf-8"),
                msg=raw_body,
                digestmod=hashlib.sha256,
            ).hexdigest()
            is_valid = hmac.compare_digest(expected_signature, signature)
            if not is_valid:
                logger.warning("Razorpay webhook signature mismatch")
            return is_valid
        except Exception as exc:
            logger.exception("Webhook signature verification failed: %s", exc)
            return False

    def simulate_test_webhook_payload(
        self,
        sale_id: str,
        amount: float,
        payment_link_id: Optional[str] = None,
        status: str = "captured"
    ) -> Dict[str, Any]:
        """
        Helper to construct a realistic Razorpay webhook payload for test/demo simulations.
        """
        pay_id = f"pay_{uuid.uuid4().hex[:14]}"
        link_id = payment_link_id or f"plink_{uuid.uuid4().hex[:14]}"
        amount_paise = int(round(amount * 100))

        return {
            "entity": "event",
            "account_id": "acc_voiceledger_test",
            "event": "payment_link.paid" if status == "captured" else "payment.failed",
            "contains": ["payment", "payment_link"],
            "payload": {
                "payment_link": {
                    "entity": {
                        "id": link_id,
                        "amount": amount_paise,
                        "amount_paid": amount_paise,
                        "status": "paid" if status == "captured" else "partially_paid",
                        "notes": {"sale_id": sale_id}
                    }
                },
                "payment": {
                    "entity": {
                        "id": pay_id,
                        "amount": amount_paise,
                        "currency": "INR",
                        "status": status,
                        "method": "upi",
                        "vpa": "customer@okhdfcbank",
                        "notes": {"sale_id": sale_id}
                    }
                }
            },
            "created_at": 1740000000
        }


razorpay_service = RazorpayService()
