from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
import httpx
import pytest

from backend.app.config import settings
from backend.app.models.payment import PaymentStatus
from backend.app.providers.exceptions import (
    ProviderAuthenticationError,
    ProviderResourceNotFoundError,
    ProviderUnavailableError,
    ProviderValidationError,
)
from backend.app.providers.schemas import (
    NormalizedPayment,
    NormalizedPaymentEvent,
    PaymentMethodType,
)
from backend.app.providers.razorpay.client import RazorpayClient
from backend.app.providers.razorpay.adapter import RazorpayProvider


# =====================================================================
# Fixtures & Sample Payloads
# =====================================================================

@pytest.fixture
def sample_razorpay_payment_dict():
    """Standard captured UPI payment payload from Razorpay."""
    return {
        "id": "pay_K839Xsk92Nd",
        "entity": "payment",
        "amount": 75000,  # 750.00 INR (paise)
        "currency": "INR",
        "status": "captured",
        "order_id": "order_J839Xksd82",
        "invoice_id": None,
        "international": False,
        "method": "upi",
        "amount_refunded": 0,
        "refund_status": None,
        "captured": True,
        "description": "Kirana Store Order #104",
        "card_id": None,
        "bank": None,
        "wallet": None,
        "vpa": "merchant_customer@okhdfcbank",
        "email": "customer@example.com",
        "contact": "+919876543210",
        "notes": {"store_id": "kirana_001"},
        "fee": 150,
        "tax": 27,
        "created_at": 1700000000,
    }


@pytest.fixture
def mock_client():
    """Client with test credentials."""
    return RazorpayClient(key_id="rzp_test_mockKey123", key_secret="mock_secret_abc456")


# =====================================================================
# 1. Configuration & Credential Safety Tests
# =====================================================================

def test_missing_credentials_raise_authentication_error():
    """Client without key_id or key_secret raises ProviderAuthenticationError before making network requests."""
    client = RazorpayClient(key_id="", key_secret="")
    with pytest.raises(ProviderAuthenticationError) as exc:
        client.get_payment("pay_test_123")
    assert "not configured" in str(exc.value)
    assert exc.value.provider == "RAZORPAY"


def test_credentials_loaded_from_settings_by_default(monkeypatch):
    """Client falls back to settings.RAZORPAY_KEY_ID / KEY_SECRET when not passed explicitly."""
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", "rzp_test_settings_key")
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", "settings_secret_xyz")

    client = RazorpayClient()
    assert client._key_id == "rzp_test_settings_key"
    assert client._key_secret == "settings_secret_xyz"


def test_secrets_never_exposed_in_repr_or_str(mock_client):
    """Secret key is never printed in client string representations."""
    repr_str = repr(mock_client)
    assert "mock_secret_abc456" not in repr_str
    assert "rzp_test" in repr_str


def test_invalid_payment_id_rejected_early(mock_client):
    """Empty or non-string payment ID fails with ProviderValidationError."""
    with pytest.raises(ProviderValidationError):
        mock_client.get_payment("")  # type: ignore

    with pytest.raises(ProviderValidationError):
        mock_client.get_payment(None)  # type: ignore


# =====================================================================
# 2. Client HTTP & Network Failure Handling Tests
# =====================================================================

def test_client_successful_200_response(mock_client, sample_razorpay_payment_dict):
    """HTTP 200 response returns parsed payment dictionary."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = sample_razorpay_payment_dict

    with patch.object(httpx.Client, "get", return_value=mock_response):
        result = mock_client.get_payment("pay_K839Xsk92Nd")
        assert result["id"] == "pay_K839Xsk92Nd"
        assert result["amount"] == 75000
        assert result["status"] == "captured"


def test_client_authentication_failure_401(mock_client):
    """HTTP 401 raises ProviderAuthenticationError without exposing the secret."""
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.json.return_value = {"error": {"description": "Invalid API key"}}

    with patch.object(httpx.Client, "get", return_value=mock_response):
        with pytest.raises(ProviderAuthenticationError) as exc:
            mock_client.get_payment("pay_test_123")
        assert exc.value.provider == "RAZORPAY"
        assert "mock_secret" not in str(exc.value)


def test_client_not_found_404(mock_client):
    """HTTP 404 raises ProviderResourceNotFoundError."""
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.json.return_value = {"error": {"description": "The id provided does not exist"}}

    with patch.object(httpx.Client, "get", return_value=mock_response):
        with pytest.raises(ProviderResourceNotFoundError) as exc:
            mock_client.get_payment("pay_nonexistent")
        assert exc.value.provider == "RAZORPAY"
        assert "pay_nonexistent" in str(exc.value)


def test_client_validation_error_400(mock_client):
    """HTTP 400 raises ProviderValidationError."""
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"error": {"description": "Bad Request parameters"}}

    with patch.object(httpx.Client, "get", return_value=mock_response):
        with pytest.raises(ProviderValidationError) as exc:
            mock_client.get_payment("pay_bad_request")
        assert exc.value.provider == "RAZORPAY"
        assert "Bad Request parameters" in str(exc.value)


def test_client_server_error_500(mock_client):
    """HTTP 500 raises ProviderUnavailableError."""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.json.return_value = {"error": {"description": "Internal Server Error"}}

    with patch.object(httpx.Client, "get", return_value=mock_response):
        with pytest.raises(ProviderUnavailableError) as exc:
            mock_client.get_payment("pay_server_error")
        assert exc.value.provider == "RAZORPAY"


def test_client_network_timeout(mock_client):
    """TimeoutException raises ProviderUnavailableError."""
    with patch.object(httpx.Client, "get", side_effect=httpx.TimeoutException("Connection timed out")):
        with pytest.raises(ProviderUnavailableError) as exc:
            mock_client.get_payment("pay_timeout")
        assert exc.value.provider == "RAZORPAY"
        assert "timed out" in str(exc.value).lower()


def test_client_network_connect_error(mock_client):
    """Network connection error raises ProviderUnavailableError."""
    with patch.object(httpx.Client, "get", side_effect=httpx.ConnectError("Connection refused")):
        with pytest.raises(ProviderUnavailableError) as exc:
            mock_client.get_payment("pay_conn_err")
        assert exc.value.provider == "RAZORPAY"


def test_client_malformed_json_response(mock_client):
    """Non-JSON or invalid response raises ProviderValidationError."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("Invalid JSON")
    mock_response.text = "<html>502 Bad Gateway</html>"

    with patch.object(httpx.Client, "get", return_value=mock_response):
        with pytest.raises(ProviderValidationError) as exc:
            mock_client.get_payment("pay_bad_json")
        assert exc.value.provider == "RAZORPAY"


def test_client_unexpected_status_code(mock_client):
    """Unexpected HTTP status (e.g. 502) raises ProviderUnavailableError."""
    mock_response = MagicMock()
    mock_response.status_code = 502
    mock_response.json.return_value = {"error": "Bad Gateway"}

    with patch.object(httpx.Client, "get", return_value=mock_response):
        with pytest.raises(ProviderUnavailableError) as exc:
            mock_client.get_payment("pay_unexpected_status")
        assert exc.value.provider == "RAZORPAY"


# =====================================================================
# 3. RazorpayProvider Adapter Normalization Tests
# =====================================================================

def test_adapter_fetch_and_normalize_captured_payment(mock_client, sample_razorpay_payment_dict):
    """Full adapter flow: fetches raw payload via client and returns NormalizedPayment."""
    provider = RazorpayProvider(client=mock_client)
    assert provider.provider_name == "RAZORPAY"

    with patch.object(mock_client, "get_payment", return_value=sample_razorpay_payment_dict):
        payment = provider.fetch_payment("pay_K839Xsk92Nd")

        assert isinstance(payment, NormalizedPayment)
        assert payment.provider == "RAZORPAY"
        assert payment.provider_payment_id == "pay_K839Xsk92Nd"
        assert payment.provider_order_id == "order_J839Xksd82"
        assert payment.amount_minor == 75000  # Exact paise, integer
        assert payment.currency == "INR"
        assert payment.status == PaymentStatus.CAPTURED
        assert payment.payment_method == PaymentMethodType.UPI
        assert payment.payer_reference == "merchant_customer@okhdfcbank"
        assert payment.captured_at == datetime.fromtimestamp(1700000000, tz=timezone.utc)


def test_adapter_verify_payment_status_server_to_server(mock_client, sample_razorpay_payment_dict):
    """verify_payment_status performs authoritative server-side check with Razorpay."""
    provider = RazorpayProvider(client=mock_client)

    with patch.object(mock_client, "get_payment", return_value=sample_razorpay_payment_dict):
        verified = provider.verify_payment_status("pay_K839Xsk92Nd")
        assert verified.status == PaymentStatus.CAPTURED
        assert verified.amount_minor == 75000


def test_amount_handling_rejects_floats(mock_client, sample_razorpay_payment_dict):
    """Floating point amounts in Razorpay payload are strictly rejected."""
    provider = RazorpayProvider(client=mock_client)
    bad_payload = dict(sample_razorpay_payment_dict)
    bad_payload["amount"] = 750.50  # Float prohibited!

    with pytest.raises(ProviderValidationError) as exc:
        provider.normalize_payment_payload(bad_payload)
    assert "amount must be a non-negative integer" in str(exc.value)


def test_amount_handling_rejects_negative_amounts(mock_client, sample_razorpay_payment_dict):
    """Negative amounts are strictly rejected."""
    provider = RazorpayProvider(client=mock_client)
    bad_payload = dict(sample_razorpay_payment_dict)
    bad_payload["amount"] = -100

    with pytest.raises(ProviderValidationError) as exc:
        provider.normalize_payment_payload(bad_payload)
    assert "amount must be a non-negative integer" in str(exc.value)


def test_status_mapping_authorized(mock_client, sample_razorpay_payment_dict):
    """Razorpay 'authorized' maps to PaymentStatus.AUTHORIZED."""
    provider = RazorpayProvider(client=mock_client)
    payload = dict(sample_razorpay_payment_dict)
    payload["status"] = "authorized"
    payload["captured"] = False

    payment = provider.normalize_payment_payload(payload)
    assert payment.status == PaymentStatus.AUTHORIZED
    assert payment.captured_at is None


def test_status_mapping_created(mock_client, sample_razorpay_payment_dict):
    """Razorpay 'created' maps to PaymentStatus.CREATED."""
    provider = RazorpayProvider(client=mock_client)
    payload = dict(sample_razorpay_payment_dict)
    payload["status"] = "created"
    payload["captured"] = False

    payment = provider.normalize_payment_payload(payload)
    assert payment.status == PaymentStatus.CREATED


def test_status_mapping_failed(mock_client, sample_razorpay_payment_dict):
    """Razorpay 'failed' maps to PaymentStatus.FAILED."""
    provider = RazorpayProvider(client=mock_client)
    payload = dict(sample_razorpay_payment_dict)
    payload["status"] = "failed"
    payload["captured"] = False

    payment = provider.normalize_payment_payload(payload)
    assert payment.status == PaymentStatus.FAILED


def test_status_mapping_full_refund(mock_client, sample_razorpay_payment_dict):
    """Razorpay 'refunded' with full amount maps to PaymentStatus.REFUNDED."""
    provider = RazorpayProvider(client=mock_client)
    payload = dict(sample_razorpay_payment_dict)
    payload["status"] = "refunded"
    payload["amount_refunded"] = 75000

    payment = provider.normalize_payment_payload(payload)
    assert payment.status == PaymentStatus.REFUNDED


def test_status_mapping_partial_refund(mock_client, sample_razorpay_payment_dict):
    """Razorpay 'refunded' with partial amount maps to PaymentStatus.PARTIALLY_REFUNDED."""
    provider = RazorpayProvider(client=mock_client)
    payload = dict(sample_razorpay_payment_dict)
    payload["status"] = "refunded"
    payload["amount_refunded"] = 30000  # Less than total 75000

    payment = provider.normalize_payment_payload(payload)
    assert payment.status == PaymentStatus.PARTIALLY_REFUNDED


def test_unsupported_status_raises_validation_error(mock_client, sample_razorpay_payment_dict):
    """Unknown or unhandled Razorpay status fails safely and explicitly."""
    provider = RazorpayProvider(client=mock_client)
    payload = dict(sample_razorpay_payment_dict)
    payload["status"] = "under_manual_review"

    with pytest.raises(ProviderValidationError) as exc:
        provider.normalize_payment_payload(payload)
    assert "Unsupported or unrecognized Razorpay payment status" in str(exc.value)


def test_payment_methods_mapping(mock_client, sample_razorpay_payment_dict):
    """Razorpay payment methods map to canonical PaymentMethodType."""
    provider = RazorpayProvider(client=mock_client)

    methods = {
        "card": PaymentMethodType.CARD,
        "netbanking": PaymentMethodType.NETBANKING,
        "wallet": PaymentMethodType.WALLET,
        "qr": PaymentMethodType.QR,
        "upi_qr": PaymentMethodType.QR,
        "bank_transfer": PaymentMethodType.BANK_TRANSFER,
        "unknown_gateway_type": PaymentMethodType.UNKNOWN,
    }
    for rzp_method, expected_type in methods.items():
        payload = dict(sample_razorpay_payment_dict)
        payload["method"] = rzp_method
        payment = provider.normalize_payment_payload(payload)
        assert payment.payment_method == expected_type


def test_payer_reference_fallbacks(mock_client, sample_razorpay_payment_dict):
    """Payer reference falls back to contact or email if VPA is absent."""
    provider = RazorpayProvider(client=mock_client)

    # Card payment with contact
    payload_card = dict(sample_razorpay_payment_dict)
    payload_card["method"] = "card"
    payload_card["vpa"] = None
    payload_card["contact"] = "+919876543210"
    payment = provider.normalize_payment_payload(payload_card)
    assert payment.payer_reference == "+919876543210"

    # Card payment with email only
    payload_email = dict(sample_razorpay_payment_dict)
    payload_email["method"] = "card"
    payload_email["vpa"] = None
    payload_email["contact"] = None
    payload_email["email"] = "shopper@domain.com"
    payment_email = provider.normalize_payment_payload(payload_email)
    assert payment_email.payer_reference == "shopper@domain.com"


def test_normalize_event_payload(mock_client, sample_razorpay_payment_dict):
    """Webhook event payload is properly normalized for Level 1 idempotency tracking."""
    provider = RazorpayProvider(client=mock_client)

    webhook_payload = {
        "entity": "event",
        "account_id": "acc_BFs892kds9",
        "event": "payment.captured",
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": sample_razorpay_payment_dict
            }
        },
        "created_at": 1700000000,
    }

    event = provider.normalize_event_payload(webhook_payload)
    assert isinstance(event, NormalizedPaymentEvent)
    assert event.provider == "RAZORPAY"
    assert event.event_type == "payment.captured"
    assert event.provider_payment_id == "pay_K839Xsk92Nd"
    assert event.payment is not None
    assert event.payment.status == PaymentStatus.CAPTURED
    assert len(event.raw_payload_hash) == 64


# =====================================================================
# 4. Security & Sensitive Data Leakage Prevention Tests
# =====================================================================

def test_credentials_never_appear_in_exceptions_or_logs(mock_client, caplog):
    """Ensure key_secret does not leak into exception text or captured logs."""
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.json.return_value = {"error": {"description": "Invalid key_secret provided"}}

    with patch.object(httpx.Client, "get", return_value=mock_response):
        with pytest.raises(ProviderAuthenticationError) as exc:
            mock_client.get_payment("pay_leak_test")

        # Verify raw secret is absent from exception and logs
        assert "mock_secret_abc456" not in str(exc.value)
        assert "mock_secret_abc456" not in caplog.text


def test_raw_metadata_sensitive_keys_redacted(mock_client, sample_razorpay_payment_dict):
    """Verify sensitive fields in raw_metadata are sanitized."""
    provider = RazorpayProvider(client=mock_client)
    payload = dict(sample_razorpay_payment_dict)
    payload["notes"] = {"key_secret": "sensitive_val", "password": "pass"}

    payment = provider.normalize_payment_payload(payload)
    assert payment.raw_metadata is not None
    assert payment.raw_metadata["notes"]["key_secret"] == "[REDACTED]"
    assert payment.raw_metadata["notes"]["password"] == "[REDACTED]"
