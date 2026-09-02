import hashlib
import hmac
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.config import settings
from backend.app.db.session import get_db
from backend.app.models.payment import Payment
from backend.app.models.payment_event import PaymentEvent
from backend.app.models.voice_notification import VoiceNotification
from backend.app.providers.exceptions import (
    ProviderAuthenticationError,
    ProviderValidationError,
)
from backend.app.providers.razorpay.webhook import RazorpayWebhookVerifier
from backend.app.providers.razorpay.adapter import RazorpayProvider

# PostgreSQL session for database immutability verification
pg_engine = create_engine(settings.DATABASE_URL)
PGTestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)


@pytest.fixture
def pg_db():
    connection = pg_engine.connect()
    transaction = connection.begin()
    session = PGTestSessionLocal(bind=connection)
    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


@pytest.fixture
def client(pg_db):
    def override_get_db():
        yield pg_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


TEST_WEBHOOK_SECRET = "whsec_test_VoiceLedgerSecret2026!#"
ALTERNATIVE_SECRET = "whsec_different_secret_99887766!#"


@pytest.fixture
def verifier():
    return RazorpayWebhookVerifier(webhook_secret=TEST_WEBHOOK_SECRET)


@pytest.fixture
def sample_payload_bytes():
    payload = {
        "id": "evt_test_001",
        "entity": "event",
        "account_id": "acc_BFs892kds9",
        "event": "payment.captured",
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_Wh9384Ksdk92",
                    "entity": "payment",
                    "amount": 50000,
                    "currency": "INR",
                    "status": "captured",
                    "order_id": "order_H8394Xsd9",
                    "method": "upi",
                    "vpa": "payer@okhdfcbank",
                }
            }
        },
        "created_at": 1700000000,
    }
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def generate_signature(raw_bytes: bytes, secret: str = TEST_WEBHOOK_SECRET) -> str:
    return hmac.new(
        key=secret.encode("utf-8"),
        msg=raw_bytes,
        digestmod=hashlib.sha256,
    ).hexdigest()


# =====================================================================
# 1. Cryptographic Signature Verification Tests (1-9)
# =====================================================================

def test_valid_razorpay_signature_accepted(verifier, sample_payload_bytes):
    """1. Valid HMAC-SHA256 signature is accepted."""
    valid_sig = generate_signature(sample_payload_bytes, TEST_WEBHOOK_SECRET)
    assert verifier.verify_signature(sample_payload_bytes, valid_sig) is True


def test_invalid_signature_rejected(verifier, sample_payload_bytes):
    """2. Tampered or arbitrary signature is rejected."""
    invalid_sig = "a" * 64
    assert verifier.verify_signature(sample_payload_bytes, invalid_sig) is False


def test_wrong_secret_rejected(verifier, sample_payload_bytes):
    """3. Signature generated with a different secret is rejected."""
    wrong_secret_sig = generate_signature(sample_payload_bytes, ALTERNATIVE_SECRET)
    assert verifier.verify_signature(sample_payload_bytes, wrong_secret_sig) is False


def test_modified_payload_rejected(verifier, sample_payload_bytes):
    """4. Signature generated for payload A fails when presented with modified payload B."""
    original_sig = generate_signature(sample_payload_bytes, TEST_WEBHOOK_SECRET)

    # Attacker attempts to change amount: 50000 -> 500000 (T4 threat model)
    modified_bytes = sample_payload_bytes.replace(b"50000", b"500000")
    assert verifier.verify_signature(modified_bytes, original_sig) is False


def test_missing_signature_rejected(verifier, sample_payload_bytes):
    """5. None or missing signature is rejected."""
    assert verifier.verify_signature(sample_payload_bytes, None) is False


def test_empty_signature_rejected(verifier, sample_payload_bytes):
    """6. Empty signature string is rejected."""
    assert verifier.verify_signature(sample_payload_bytes, "") is False
    assert verifier.verify_signature(sample_payload_bytes, "   ") is False


def test_malformed_signature_rejected_safely(verifier, sample_payload_bytes):
    """7. Malformed signature string (e.g. non-hex, special characters) fails safely without crashing."""
    malformed_signatures = [
        "not_a_hex_signature_at_all!",
        "123",
        "zzz" * 20,
        "\x00\x01\x02",
        "SELECT * FROM webhooks;",
    ]
    for bad_sig in malformed_signatures:
        assert verifier.verify_signature(sample_payload_bytes, bad_sig) is False


def test_exact_raw_body_integrity(verifier, sample_payload_bytes):
    """8. Exact raw body bytes are required; any whitespace or formatting difference invalidates the signature."""
    valid_sig = generate_signature(sample_payload_bytes, TEST_WEBHOOK_SECRET)

    # Appending a trailing space or newline to the body
    with_trailing_space = sample_payload_bytes + b" "
    with_newline = sample_payload_bytes + b"\n"

    assert verifier.verify_signature(with_trailing_space, valid_sig) is False
    assert verifier.verify_signature(with_newline, valid_sig) is False


def test_webhook_secret_never_appears_in_errors_logs_or_repr(verifier, caplog):
    """9. Webhook secret is masked and never exposed in repr or error messages."""
    repr_str = repr(verifier)
    assert TEST_WEBHOOK_SECRET not in repr_str
    assert "whse..." in repr_str

    # Test error handling when unconfigured
    empty_verifier = RazorpayWebhookVerifier(webhook_secret="")
    with pytest.raises(ProviderAuthenticationError) as exc:
        empty_verifier.verify_and_parse(b"{}", "sig")
    assert "not configured" in str(exc.value)
    assert TEST_WEBHOOK_SECRET not in caplog.text


# =====================================================================
# 2. HTTP Endpoint Verification Tests (10-13)
# =====================================================================

def test_endpoint_rejects_unsigned_requests(client, sample_payload_bytes):
    """10. Endpoint rejects request missing X-Razorpay-Signature header with 401."""
    res = client.post(
        "/api/v1/webhooks/razorpay",
        content=sample_payload_bytes,
        headers={"Content-Type": "application/json"},
    )
    assert res.status_code == 401
    assert "Invalid or missing webhook signature" in res.json()["detail"]


def test_endpoint_accepts_correctly_signed_requests(client, sample_payload_bytes, monkeypatch):
    """11. Endpoint accepts correctly signed webhook with 200 OK."""
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    signature = generate_signature(sample_payload_bytes, TEST_WEBHOOK_SECRET)
    res = client.post(
        "/api/v1/webhooks/razorpay",
        content=sample_payload_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signature,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "accepted"
    assert data["verified"] is True
    assert data["event"] == "payment.captured"
    assert data["event_id"] == "evt_test_001"


def test_valid_webhook_does_not_mutate_financial_ledger_yet(client, pg_db, sample_payload_bytes, monkeypatch):
    """12. Financial boundary check: a verified webhook persists PaymentEvent but strictly DOES NOT create Payment or VoiceNotification records."""
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    # Initial counts
    init_payments = pg_db.query(Payment).count()
    init_events = pg_db.query(PaymentEvent).count()
    init_notifs = pg_db.query(VoiceNotification).count()

    signature = generate_signature(sample_payload_bytes, TEST_WEBHOOK_SECRET)
    res = client.post(
        "/api/v1/webhooks/razorpay",
        content=sample_payload_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signature,
        },
    )
    assert res.status_code == 200

    # Verify PaymentEvent was recorded, but financial tables (Payment, VoiceNotification) remain untouched!
    assert pg_db.query(Payment).count() == init_payments
    assert pg_db.query(VoiceNotification).count() == init_notifs
    assert pg_db.query(PaymentEvent).count() == init_events + 1


def test_endpoint_rejects_oversized_webhook_payloads(client):
    """13. Webhook payload exceeding size limit (1 MB) is rejected with 413."""
    oversized_body = b"x" * (1024 * 1024 + 10)
    res = client.post(
        "/api/v1/webhooks/razorpay",
        content=oversized_body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": "sig123",
        },
    )
    assert res.status_code == 413


def test_razorpay_provider_adapter_webhook_delegation(sample_payload_bytes):
    """14. RazorpayProvider.verify_webhook delegates accurately to the verifier."""
    custom_verifier = RazorpayWebhookVerifier(webhook_secret=TEST_WEBHOOK_SECRET)
    provider = RazorpayProvider(verifier=custom_verifier)

    valid_sig = generate_signature(sample_payload_bytes, TEST_WEBHOOK_SECRET)
    invalid_sig = generate_signature(sample_payload_bytes, ALTERNATIVE_SECRET)

    assert provider.verify_webhook(sample_payload_bytes, valid_sig) is True
    assert provider.verify_webhook(sample_payload_bytes, invalid_sig) is False
