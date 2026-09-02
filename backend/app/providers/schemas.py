"""
VoiceLedger Provider-Independent Normalized Data Structures.

Guarantees that VoiceLedger's payment core and ledger models work exclusively with
normalized, strongly-typed representations rather than vendor-specific JSON payloads.
"""
from datetime import datetime
import enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.models.payment import PaymentStatus
from backend.app.core.security import sanitize_sensitive_data


class PaymentMethodType(str, enum.Enum):
    """Normalized payment instrument/channel types."""
    UPI = "UPI"
    CARD = "CARD"
    NETBANKING = "NETBANKING"
    WALLET = "WALLET"
    QR = "QR"
    BANK_TRANSFER = "BANK_TRANSFER"
    UNKNOWN = "UNKNOWN"


class NormalizedPayment(BaseModel):
    """
    Canonical, provider-independent representation of a verified payment transaction.

    Rules:
    - Amounts are strictly non-negative integer minor units (e.g. paise for INR).
    - Floating point money is strictly prohibited.
    - Currencies are normalized to 3-character uppercase ISO codes.
    - Raw metadata is automatically scrubbed of sensitive credentials/secrets.
    """
    provider: str = Field(..., min_length=1, description="Identifier of the payment provider, e.g. 'RAZORPAY'")
    provider_payment_id: str = Field(..., min_length=1, description="Unique transaction ID at the provider")
    provider_order_id: Optional[str] = Field(None, description="Optional upstream order/intent reference")
    amount_minor: int = Field(..., ge=0, description="Amount in integer minor units (paise)")
    currency: str = Field(default="INR", min_length=3, max_length=3, description="ISO 4217 currency code")
    status: PaymentStatus = Field(..., description="Canonical VoiceLedger payment status")
    payment_method: PaymentMethodType = Field(default=PaymentMethodType.UNKNOWN, description="Payment instrument channel")
    payer_reference: Optional[str] = Field(None, description="Identifier for the payer (e.g. UPI VPA, phone, masked card)")
    captured_at: Optional[datetime] = Field(None, description="Timestamp when the payment was captured at provider")
    provider_created_at: Optional[datetime] = Field(None, description="Timestamp when the payment was created at provider")
    raw_metadata: Optional[Dict[str, Any]] = Field(None, description="Sanitized provider metadata for audit logs")

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, v: Any) -> str:
        if isinstance(v, str):
            clean = v.strip().upper()
            if len(clean) == 3:
                return clean
        raise ValueError("Currency must be a valid 3-letter ISO code (e.g. 'INR')")

    @field_validator("raw_metadata", mode="before")
    @classmethod
    def sanitize_metadata(cls, v: Any) -> Optional[Dict[str, Any]]:
        if v is None:
            return None
        if isinstance(v, dict):
            return sanitize_sensitive_data(v)
        return {"data": str(v)}


class NormalizedPaymentEvent(BaseModel):
    """
    Canonical, provider-independent representation of an inbound payment event/webhook.
    """
    provider: str = Field(..., min_length=1, description="Provider origin")
    event_id: str = Field(..., min_length=1, description="Unique event identifier for Level 1 idempotency")
    event_type: str = Field(..., min_length=1, description="Canonical event category, e.g. 'payment.captured'")
    payment: Optional[NormalizedPayment] = Field(None, description="Associated normalized payment payload if applicable")
    provider_payment_id: Optional[str] = Field(None, description="Payment ID associated with the event")
    timestamp: datetime = Field(..., description="Timestamp of the event dispatch")
    raw_payload_hash: str = Field(..., description="SHA-256 fingerprint of the raw payload for tamper audit")

    model_config = ConfigDict(extra="forbid", frozen=True)
