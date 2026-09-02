"""
VoiceLedger Razorpay Provider Adapter.

Implements the PaymentProvider interface for Razorpay, translating vendor-specific
wire payloads, status codes, and identifiers into VoiceLedger's canonical normalized domain.
"""
from datetime import datetime, timezone
import hashlib
from typing import Dict, Any, Optional

from backend.app.models.payment import PaymentStatus
from backend.app.providers.base import PaymentProvider
from backend.app.providers.exceptions import ProviderValidationError
from backend.app.providers.schemas import (
    NormalizedPayment,
    NormalizedPaymentEvent,
    PaymentMethodType,
)
from backend.app.providers.razorpay.client import RazorpayClient
from backend.app.providers.razorpay.webhook import RazorpayWebhookVerifier


# Authoritative mapping from Razorpay payment statuses to VoiceLedger PaymentStatus
RAZORPAY_STATUS_MAP: Dict[str, PaymentStatus] = {
    "created": PaymentStatus.CREATED,
    "authorized": PaymentStatus.AUTHORIZED,
    "captured": PaymentStatus.CAPTURED,
    "failed": PaymentStatus.FAILED,
}

# Mapping from Razorpay payment instruments to canonical PaymentMethodType
RAZORPAY_METHOD_MAP: Dict[str, PaymentMethodType] = {
    "upi": PaymentMethodType.UPI,
    "card": PaymentMethodType.CARD,
    "netbanking": PaymentMethodType.NETBANKING,
    "wallet": PaymentMethodType.WALLET,
    "qr": PaymentMethodType.QR,
    "upi_qr": PaymentMethodType.QR,
    "bank_transfer": PaymentMethodType.BANK_TRANSFER,
}


class RazorpayProvider(PaymentProvider):
    """
    Concrete PaymentProvider adapter for Razorpay.
    """
    PROVIDER_NAME: str = "RAZORPAY"

    def __init__(
        self,
        client: Optional[RazorpayClient] = None,
        verifier: Optional[RazorpayWebhookVerifier] = None,
    ):
        self._client = client or RazorpayClient()
        self._verifier = verifier or RazorpayWebhookVerifier()

    @property
    def provider_name(self) -> str:
        return self.PROVIDER_NAME

    @property
    def client(self) -> RazorpayClient:
        return self._client

    @property
    def verifier(self) -> RazorpayWebhookVerifier:
        return self._verifier

    def verify_webhook(self, raw_body: bytes, signature: str) -> bool:
        """
        Verify incoming Razorpay webhook signature against exact raw request body.
        """
        return self._verifier.verify_signature(raw_body, signature)

    def fetch_payment(self, provider_payment_id: str) -> NormalizedPayment:
        """
        Fetch payment details directly from Razorpay by transaction ID.
        """
        raw_payload = self._client.get_payment(provider_payment_id)
        return self.normalize_payment_payload(raw_payload)

    def verify_payment_status(self, provider_payment_id: str) -> NormalizedPayment:
        """
        Server-to-server verification of current payment status with Razorpay.
        Guarantees that client-reported payment states are never trusted blindly.
        """
        return self.fetch_payment(provider_payment_id)

    def normalize_payment_payload(self, raw_payload: Dict[str, Any]) -> NormalizedPayment:
        """
        Convert a raw Razorpay payment dictionary into canonical NormalizedPayment.
        """
        if not isinstance(raw_payload, dict):
            raise ProviderValidationError(
                "Invalid Razorpay payload: expected dictionary",
                provider=self.PROVIDER_NAME,
            )

        # 1. Validate payment identifier
        payment_id = raw_payload.get("id")
        if not payment_id or not isinstance(payment_id, str):
            raise ProviderValidationError(
                "Razorpay payload missing required string 'id'",
                provider=self.PROVIDER_NAME,
                raw_response=raw_payload,
            )

        # 2. Validate amount in integer minor units (paise)
        raw_amount = raw_payload.get("amount")
        if (
            raw_amount is None
            or not isinstance(raw_amount, int)
            or isinstance(raw_amount, bool)
            or raw_amount < 0
        ):
            raise ProviderValidationError(
                f"Razorpay amount must be a non-negative integer minor unit (paise), got: {raw_amount!r}",
                provider=self.PROVIDER_NAME,
                raw_response=raw_payload,
            )

        # 3. Currency
        currency = raw_payload.get("currency", "INR")
        if not isinstance(currency, str) or len(currency.strip()) != 3:
            raise ProviderValidationError(
                f"Invalid Razorpay currency: {currency!r}",
                provider=self.PROVIDER_NAME,
                raw_response=raw_payload,
            )

        # 4. Map payment status
        raw_status = str(raw_payload.get("status", "")).lower().strip()
        if raw_status in RAZORPAY_STATUS_MAP:
            canonical_status = RAZORPAY_STATUS_MAP[raw_status]
        elif raw_status == "refunded":
            amount_refunded = raw_payload.get("amount_refunded", 0)
            if isinstance(amount_refunded, int) and 0 < amount_refunded < raw_amount:
                canonical_status = PaymentStatus.PARTIALLY_REFUNDED
            else:
                canonical_status = PaymentStatus.REFUNDED
        else:
            raise ProviderValidationError(
                f"Unsupported or unrecognized Razorpay payment status: {raw_status!r}",
                provider=self.PROVIDER_NAME,
                raw_response=raw_payload,
            )

        # 5. Map payment method
        raw_method = str(raw_payload.get("method", "")).lower().strip()
        payment_method = RAZORPAY_METHOD_MAP.get(raw_method, PaymentMethodType.UNKNOWN)

        # 6. Extract payer reference
        payer_reference = None
        if payment_method == PaymentMethodType.UPI and raw_payload.get("vpa"):
            payer_reference = str(raw_payload["vpa"]).strip()
        elif raw_payload.get("contact"):
            payer_reference = str(raw_payload["contact"]).strip()
        elif raw_payload.get("email"):
            payer_reference = str(raw_payload["email"]).strip()

        # 7. Timestamps
        created_at = None
        raw_created_at = raw_payload.get("created_at")
        if isinstance(raw_created_at, (int, float)) and raw_created_at > 0:
            try:
                created_at = datetime.fromtimestamp(int(raw_created_at), tz=timezone.utc)
            except (ValueError, OSError):
                created_at = None

        captured_at = created_at if canonical_status == PaymentStatus.CAPTURED else None

        # 8. Order reference
        order_id = raw_payload.get("order_id")
        clean_order_id = str(order_id).strip() if order_id else None

        return NormalizedPayment(
            provider=self.PROVIDER_NAME,
            provider_payment_id=payment_id.strip(),
            provider_order_id=clean_order_id,
            amount_minor=raw_amount,
            currency=currency.strip().upper(),
            status=canonical_status,
            payment_method=payment_method,
            payer_reference=payer_reference,
            captured_at=captured_at,
            provider_created_at=created_at,
            raw_metadata=raw_payload,
        )

    def normalize_event_payload(
        self,
        raw_payload: Dict[str, Any],
        raw_payload_bytes: Optional[bytes] = None,
    ) -> NormalizedPaymentEvent:
        """
        Normalize inbound Razorpay webhook payload for Level 1 idempotency tracking.
        """
        if not isinstance(raw_payload, dict):
            raise ProviderValidationError(
                "Invalid Razorpay event payload: expected dictionary",
                provider=self.PROVIDER_NAME,
            )

        # Hash raw bytes for tamper-detection / idempotency audit
        payload_bytes = raw_payload_bytes or str(raw_payload).encode("utf-8")
        raw_hash = hashlib.sha256(payload_bytes).hexdigest()

        event_type = raw_payload.get("event", "unknown")
        # In Razorpay webhooks, payment entity is under payload.payment.entity
        payment_entity = (
            raw_payload.get("payload", {})
            .get("payment", {})
            .get("entity")
        )

        normalized_payment = None
        provider_payment_id = None
        if isinstance(payment_entity, dict):
            normalized_payment = self.normalize_payment_payload(payment_entity)
            provider_payment_id = normalized_payment.provider_payment_id

        # Unique event identifier
        event_id = raw_payload.get("id") or f"evt_{raw_hash[:16]}"

        raw_created_at = raw_payload.get("created_at")
        event_timestamp = datetime.now(timezone.utc)
        if isinstance(raw_created_at, (int, float)) and raw_created_at > 0:
            try:
                event_timestamp = datetime.fromtimestamp(int(raw_created_at), tz=timezone.utc)
            except (ValueError, OSError):
                pass

        return NormalizedPaymentEvent(
            provider=self.PROVIDER_NAME,
            event_id=str(event_id),
            event_type=str(event_type),
            payment=normalized_payment,
            provider_payment_id=provider_payment_id,
            timestamp=event_timestamp,
            raw_payload_hash=raw_hash,
        )
