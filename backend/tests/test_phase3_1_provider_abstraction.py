import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import pytest
from pydantic import ValidationError

from backend.app.models.payment import PaymentStatus
from backend.app.providers import (
    PaymentProvider,
    NormalizedPayment,
    NormalizedPaymentEvent,
    PaymentMethodType,
    ProviderError,
    ProviderUnavailableError,
    ProviderAuthenticationError,
    ProviderResourceNotFoundError,
    ProviderValidationError,
)


# =====================================================================
# Dummy / Mock Provider Implementation for Interface Contract Testing
# =====================================================================

class MockGatewayProvider(PaymentProvider):
    """Concrete mock provider adhering to PaymentProvider interface."""

    @property
    def provider_name(self) -> str:
        return "MOCK_GATEWAY"

    def fetch_payment(self, provider_payment_id: str) -> NormalizedPayment:
        if provider_payment_id == "pay_not_found":
            raise ProviderResourceNotFoundError(
                f"Payment {provider_payment_id} not found",
                provider=self.provider_name,
            )
        if provider_payment_id == "pay_gateway_down":
            raise ProviderUnavailableError(
                "Upstream gateway timeout",
                provider=self.provider_name,
            )
        return NormalizedPayment(
            provider=self.provider_name,
            provider_payment_id=provider_payment_id,
            amount_minor=10000,
            currency="INR",
            status=PaymentStatus.CAPTURED,
            payment_method=PaymentMethodType.UPI,
        )

    def verify_payment_status(self, provider_payment_id: str) -> NormalizedPayment:
        return self.fetch_payment(provider_payment_id)

    def normalize_payment_payload(self, raw_payload: Dict[str, Any]) -> NormalizedPayment:
        return NormalizedPayment(
            provider=self.provider_name,
            provider_payment_id=raw_payload["txn_id"],
            amount_minor=int(raw_payload["cents"]),
            currency=raw_payload.get("curr", "INR"),
            status=PaymentStatus(raw_payload.get("state", "CAPTURED")),
            payment_method=PaymentMethodType(raw_payload.get("instrument", "UPI")),
            raw_metadata=raw_payload,
        )

    def normalize_event_payload(
        self,
        raw_payload: Dict[str, Any],
        raw_payload_bytes: Optional[bytes] = None,
    ) -> NormalizedPaymentEvent:
        payload_bytes = raw_payload_bytes or str(raw_payload).encode("utf-8")
        raw_hash = hashlib.sha256(payload_bytes).hexdigest()
        return NormalizedPaymentEvent(
            provider=self.provider_name,
            event_id=raw_payload["event_id"],
            event_type=raw_payload["event_name"],
            provider_payment_id=raw_payload.get("txn_id"),
            timestamp=datetime.now(timezone.utc),
            raw_payload_hash=raw_hash,
        )


# =====================================================================
# 1. Interface & Contract Compliance Tests
# =====================================================================

def test_payment_provider_interface_cannot_be_instantiated_directly():
    """Abstract interface cannot be instantiated directly."""
    with pytest.raises(TypeError) as exc:
        PaymentProvider()  # type: ignore
    assert "Can't instantiate abstract class PaymentProvider" in str(exc.value)


def test_incomplete_subclass_cannot_be_instantiated():
    """Subclass missing required abstract methods cannot be instantiated."""
    class IncompleteProvider(PaymentProvider):
        @property
        def provider_name(self) -> str:
            return "INCOMPLETE"

    with pytest.raises(TypeError) as exc:
        IncompleteProvider()  # type: ignore
    assert "Can't instantiate abstract class IncompleteProvider" in str(exc.value)


def test_concrete_provider_contract_compliance():
    """Concrete provider implements all abstract methods successfully."""
    provider = MockGatewayProvider()
    assert provider.provider_name == "MOCK_GATEWAY"

    # fetch_payment
    payment = provider.fetch_payment("pay_123456")
    assert isinstance(payment, NormalizedPayment)
    assert payment.provider == "MOCK_GATEWAY"
    assert payment.provider_payment_id == "pay_123456"
    assert payment.amount_minor == 10000
    assert payment.status == PaymentStatus.CAPTURED

    # verify_payment_status
    verified = provider.verify_payment_status("pay_123456")
    assert verified == payment

    # normalize_payment_payload
    normalized = provider.normalize_payment_payload({
        "txn_id": "txn_888",
        "cents": 55000,
        "curr": "INR",
        "state": "CAPTURED",
        "instrument": "UPI",
    })
    assert normalized.amount_minor == 55000
    assert normalized.provider_payment_id == "txn_888"

    # normalize_event_payload
    event = provider.normalize_event_payload({
        "event_id": "evt_999",
        "event_name": "payment.captured",
        "txn_id": "txn_888",
    })
    assert isinstance(event, NormalizedPaymentEvent)
    assert event.event_id == "evt_999"
    assert event.event_type == "payment.captured"
    assert len(event.raw_payload_hash) == 64


# =====================================================================
# 2. NormalizedPayment Data Structure Validation Tests
# =====================================================================

def test_normalized_payment_valid_instantiation():
    """Valid NormalizedPayment with required and optional fields."""
    now = datetime.now(timezone.utc)
    payment = NormalizedPayment(
        provider="RAZORPAY",
        provider_payment_id="pay_H93Xskd9",
        provider_order_id="order_G83jskd",
        amount_minor=50000,
        currency="INR",
        status=PaymentStatus.CAPTURED,
        payment_method=PaymentMethodType.UPI,
        payer_reference="user@okaxis",
        captured_at=now,
        provider_created_at=now,
    )
    assert payment.provider == "RAZORPAY"
    assert payment.provider_payment_id == "pay_H93Xskd9"
    assert payment.amount_minor == 50000
    assert payment.currency == "INR"
    assert payment.status == PaymentStatus.CAPTURED
    assert payment.payment_method == PaymentMethodType.UPI
    assert payment.payer_reference == "user@okaxis"


def test_normalized_payment_rejects_negative_amount():
    """Negative money amounts are strictly prohibited."""
    with pytest.raises(ValidationError) as exc:
        NormalizedPayment(
            provider="RAZORPAY",
            provider_payment_id="pay_123",
            amount_minor=-500,
            status=PaymentStatus.CAPTURED,
        )
    assert "amount_minor" in str(exc.value)


def test_normalized_payment_rejects_float_amount():
    """Floating point money amounts are strictly prohibited (integer minor units required)."""
    with pytest.raises(ValidationError) as exc:
        NormalizedPayment(
            provider="RAZORPAY",
            provider_payment_id="pay_123",
            amount_minor=500.75,  # type: ignore
            status=PaymentStatus.CAPTURED,
        )
    assert "amount_minor" in str(exc.value)


def test_normalized_payment_currency_normalization():
    """Currency is normalized to uppercase and validated as 3 characters."""
    payment = NormalizedPayment(
        provider="RAZORPAY",
        provider_payment_id="pay_123",
        amount_minor=1000,
        currency="inr",
        status=PaymentStatus.CAPTURED,
    )
    assert payment.currency == "INR"

    with pytest.raises(ValidationError):
        NormalizedPayment(
            provider="RAZORPAY",
            provider_payment_id="pay_123",
            amount_minor=1000,
            currency="INDIAN_RUPEE",
            status=PaymentStatus.CAPTURED,
        )


def test_normalized_payment_missing_required_fields():
    """Missing provider, provider_payment_id, amount_minor, or status raises ValidationError."""
    with pytest.raises(ValidationError):
        NormalizedPayment(  # Missing provider_payment_id & amount_minor
            provider="RAZORPAY",
            status=PaymentStatus.CAPTURED,
        )  # type: ignore


def test_normalized_payment_extra_fields_forbidden():
    """Arbitrary extra fields cannot be injected into NormalizedPayment."""
    with pytest.raises(ValidationError):
        NormalizedPayment(
            provider="RAZORPAY",
            provider_payment_id="pay_123",
            amount_minor=1000,
            status=PaymentStatus.CAPTURED,
            arbitrary_untrusted_field="malicious",  # type: ignore
        )


def test_normalized_payment_raw_metadata_sanitization():
    """Sensitive keys in raw_metadata are automatically redacted."""
    payment = NormalizedPayment(
        provider="RAZORPAY",
        provider_payment_id="pay_123",
        amount_minor=1000,
        status=PaymentStatus.CAPTURED,
        raw_metadata={
            "gateway_ref": "ref_999",
            "key_secret": "my_secret_token",
            "password": "my_db_password",
        },
    )
    assert payment.raw_metadata is not None
    assert payment.raw_metadata["gateway_ref"] == "ref_999"
    assert payment.raw_metadata["key_secret"] == "[REDACTED]"
    assert payment.raw_metadata["password"] == "[REDACTED]"


def test_normalized_payment_immutability():
    """NormalizedPayment is frozen and cannot be mutated."""
    payment = NormalizedPayment(
        provider="RAZORPAY",
        provider_payment_id="pay_123",
        amount_minor=1000,
        status=PaymentStatus.CAPTURED,
    )
    with pytest.raises(ValidationError):
        payment.amount_minor = 2000  # type: ignore


# =====================================================================
# 3. NormalizedPaymentEvent Validation Tests
# =====================================================================

def test_normalized_payment_event_validation():
    """Valid NormalizedPaymentEvent creation and validation."""
    now = datetime.now(timezone.utc)
    event = NormalizedPaymentEvent(
        provider="RAZORPAY",
        event_id="evt_123456",
        event_type="payment.captured",
        provider_payment_id="pay_123456",
        timestamp=now,
        raw_payload_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    assert event.provider == "RAZORPAY"
    assert event.event_id == "evt_123456"
    assert event.event_type == "payment.captured"
    assert event.provider_payment_id == "pay_123456"
    assert event.timestamp == now


def test_normalized_payment_event_missing_fields():
    """Missing required event fields raises ValidationError."""
    with pytest.raises(ValidationError):
        NormalizedPaymentEvent(
            provider="RAZORPAY",
            event_id="evt_123",
            # Missing event_type, timestamp, raw_payload_hash
        )  # type: ignore


# =====================================================================
# 4. Provider Exception Hierarchy Tests
# =====================================================================

def test_provider_exception_hierarchy():
    """Provider exceptions inherit from ProviderError and preserve metadata."""
    err = ProviderUnavailableError(
        "Connection timed out",
        provider="RAZORPAY",
        raw_response={"http_status": 504},
        error_code="GATEWAY_TIMEOUT",
    )
    assert isinstance(err, ProviderError)
    assert err.provider == "RAZORPAY"
    assert err.raw_response == {"http_status": 504}
    assert err.error_code == "GATEWAY_TIMEOUT"
    assert "Connection timed out" in str(err)

    auth_err = ProviderAuthenticationError("Bad signature", provider="RAZORPAY")
    assert isinstance(auth_err, ProviderError)

    not_found_err = ProviderResourceNotFoundError("No such payment", provider="RAZORPAY")
    assert isinstance(not_found_err, ProviderError)

    val_err = ProviderValidationError("Invalid currency", provider="RAZORPAY")
    assert isinstance(val_err, ProviderError)


def test_mock_provider_raises_correct_exceptions():
    """Provider interface calls raise specialized ProviderError subclasses."""
    provider = MockGatewayProvider()

    with pytest.raises(ProviderResourceNotFoundError) as exc:
        provider.fetch_payment("pay_not_found")
    assert exc.value.provider == "MOCK_GATEWAY"

    with pytest.raises(ProviderUnavailableError) as exc:
        provider.fetch_payment("pay_gateway_down")
    assert exc.value.provider == "MOCK_GATEWAY"


# =====================================================================
# 5. Multi-Gateway Independence & Decoupling Tests
# =====================================================================

def test_multi_gateway_normalization_independence():
    """
    Demonstrates that distinct gateway payloads (Razorpay vs Stripe vs UPI switch)
    normalize into the same canonical NormalizedPayment format without leaking
    gateway-specific schemas into the payment domain.
    """
    # 1. Razorpay-shaped payload
    rzp_raw = {
        "id": "pay_K839xjsk9",
        "entity": "payment",
        "amount": 25000,
        "currency": "INR",
        "status": "captured",
        "method": "upi",
        "vpa": "customer@okhdfcbank",
    }
    rzp_normalized = NormalizedPayment(
        provider="RAZORPAY",
        provider_payment_id=rzp_raw["id"],
        amount_minor=rzp_raw["amount"],
        currency=rzp_raw["currency"],
        status=PaymentStatus.CAPTURED,
        payment_method=PaymentMethodType.UPI,
        payer_reference=rzp_raw["vpa"],
        raw_metadata=rzp_raw,
    )

    # 2. Bank / Alternate Gateway-shaped payload
    bank_raw = {
        "transactionReference": "TXN-99881122",
        "valueInPaise": 25000,
        "curr": "INR",
        "state": "SUCCESS",
        "instrument": "UPI_INTENT",
        "payerVpa": "customer@okhdfcbank",
    }
    bank_normalized = NormalizedPayment(
        provider="DIRECT_BANK_UPI",
        provider_payment_id=bank_raw["transactionReference"],
        amount_minor=bank_raw["valueInPaise"],
        currency=bank_raw["curr"],
        status=PaymentStatus.CAPTURED,
        payment_method=PaymentMethodType.UPI,
        payer_reference=bank_raw["payerVpa"],
        raw_metadata=bank_raw,
    )

    # Both normalized representations conform to VoiceLedger core types
    assert rzp_normalized.amount_minor == bank_normalized.amount_minor
    assert rzp_normalized.currency == bank_normalized.currency
    assert rzp_normalized.status == bank_normalized.status
    assert rzp_normalized.payment_method == bank_normalized.payment_method
    assert rzp_normalized.payer_reference == bank_normalized.payer_reference
    assert rzp_normalized.provider != bank_normalized.provider


def test_payment_method_enum_values():
    """All expected canonical payment instrument types are supported."""
    assert PaymentMethodType.UPI.value == "UPI"
    assert PaymentMethodType.CARD.value == "CARD"
    assert PaymentMethodType.NETBANKING.value == "NETBANKING"
    assert PaymentMethodType.WALLET.value == "WALLET"
    assert PaymentMethodType.QR.value == "QR"
    assert PaymentMethodType.BANK_TRANSFER.value == "BANK_TRANSFER"
    assert PaymentMethodType.UNKNOWN.value == "UNKNOWN"
