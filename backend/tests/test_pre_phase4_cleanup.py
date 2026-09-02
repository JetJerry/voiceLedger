"""
VoiceLedger Pre-Phase 4 Cleanup Verification Test Suite.

Verifies that conflicting legacy financial routes (/api/auth, /api/payments, /api/webhooks)
are completely unmounted from the production FastAPI application, while the canonical
VoiceLedger v1 routes (/api/v1/auth, /api/v1/merchants, /api/v1/webhooks/razorpay)
remain fully functional and authoritative.
"""
import hashlib
import hmac
import json
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.config import settings
from backend.app.db.session import get_db
from backend.app.models.payment_event import PaymentEvent, EventProcessingStatus

pg_engine = create_engine(settings.DATABASE_URL)
PGTestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)

TEST_SECRET = "whsec_pre_phase4_cleanup_secret!#"


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


def sign(payload: bytes, secret: str = TEST_SECRET) -> str:
    return hmac.new(key=secret.encode("utf-8"), msg=payload, digestmod=hashlib.sha256).hexdigest()


# =====================================================================
# 1. Verification of Unmounted Conflicting Legacy Routes (404)
# =====================================================================

def test_legacy_auth_routes_are_unmounted(client):
    """Legacy /api/auth/login and /api/auth/register-merchant return 404."""
    res_login = client.post("/api/auth/login", json={"username": "kirana", "password": "123"})
    assert res_login.status_code == 404

    res_reg = client.post("/api/auth/register-merchant", json={"name": "Old Shop"})
    assert res_reg.status_code == 404

    res_demo = client.get("/api/auth/demo-accounts")
    assert res_demo.status_code == 404


def test_legacy_payments_routes_are_unmounted(client):
    """Legacy /api/payments/reconcile and /api/payments/link return 404."""
    res_recon = client.post("/api/payments/reconcile", json={"payment_id": "pay_1"})
    assert res_recon.status_code == 404

    res_link = client.post("/api/payments/link", json={"sale_id": "sale_1", "amount": 100.0})
    assert res_link.status_code == 404


def test_legacy_webhooks_routes_are_unmounted(client):
    """Legacy /api/webhooks/razorpay returns 404."""
    res_wh = client.post("/api/webhooks/razorpay", json={"event": "payment.captured"})
    assert res_wh.status_code == 404

    res_wh_status = client.get("/api/webhooks/status")
    assert res_wh_status.status_code == 404


# =====================================================================
# 2. Verification of Canonical v1 Production Routes (Active)
# =====================================================================

def test_canonical_v1_auth_routes_remain_mounted_and_available(client):
    """Canonical /api/v1/auth/login and register endpoints are active."""
    # Validation error (422) or Bad Request / Unauthorized confirms router is mounted and active
    res_login = client.post("/api/v1/auth/login", json={})
    assert res_login.status_code == 422  # Router is actively validating canonical request schema

    res_reg = client.post("/api/v1/auth/register", json={})
    assert res_reg.status_code == 422

    res_me = client.get("/api/v1/auth/me")
    assert res_me.status_code == 401  # HTTPBearer active


def test_canonical_v1_webhooks_endpoint_remains_active(client, pg_db, monkeypatch):
    """Canonical /api/v1/webhooks/razorpay endpoint processes and persists events."""
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", TEST_SECRET)

    event_id = f"evt_cleanup_{uuid.uuid4().hex[:10]}"
    payload = {
        "id": event_id,
        "entity": "event",
        "account_id": "acc_cleanup_test",
        "event": "payment.captured",
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_cleanup_99",
                    "amount": 20000,
                    "currency": "INR",
                    "status": "captured",
                }
            }
        },
        "created_at": 1700000000,
    }
    raw_bytes = json.dumps(payload).encode("utf-8")
    sig = sign(raw_bytes, TEST_SECRET)

    res = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "accepted"
    assert data["verified"] is True
    assert data["event_id"] == event_id
    assert data["duplicate"] is False

    # Confirms persistence in PostgreSQL
    saved = pg_db.query(PaymentEvent).filter(PaymentEvent.event_id == event_id).first()
    assert saved is not None
    assert saved.provider == "RAZORPAY"
    assert saved.event_type == "payment.captured"


def test_canonical_model_exports_only():
    """Verify backend.app.models exports strictly canonical models and zero legacy models."""
    import backend.app.models as models

    # Must contain canonical models
    assert hasattr(models, "User")
    assert hasattr(models, "Merchant")
    assert hasattr(models, "Payment")
    assert hasattr(models, "PaymentEvent")
    assert hasattr(models, "ProviderConnection")
    assert hasattr(models, "Device")
    assert hasattr(models, "VoiceNotification")

    # Must NOT export legacy models
    assert not hasattr(models, "Customer")
    assert not hasattr(models, "Product")
    assert not hasattr(models, "Sale")
    assert not hasattr(models, "SaleItem")
    assert not hasattr(models, "RecoveryAction")
    assert not hasattr(models, "MerchantProfile")
    assert not hasattr(models, "WebhookEvent")
