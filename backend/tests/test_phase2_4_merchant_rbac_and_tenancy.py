import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.config import settings
from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.models.merchant import Merchant
from backend.app.models.merchant_user import MerchantUser
from backend.app.models.payment import Payment, PaymentStatus
from backend.app.models.payment_event import PaymentEvent, EventProcessingStatus
from backend.app.models.device import Device, DeviceStatus, DeviceType
from backend.app.models.device_session import DeviceSession, DeviceSessionStatus
from backend.app.models.voice_notification import VoiceNotification, VoiceNotificationStatus
from backend.app.models.provider_connection import ProviderConnection
from backend.app.core.security import create_access_token
from backend.app.services.tenant_service import tenant_service

# PostgreSQL Engine for transactional tests
pg_engine = create_engine(settings.DATABASE_URL)
PGTestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)


@pytest.fixture
def pg_db():
    """Transactional PostgreSQL session rolled back after test completion."""
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
def pg_client(pg_db):
    """FastAPI TestClient with get_db overridden to use transactional PostgreSQL session."""
    def override_get_db():
        yield pg_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def setup_two_merchants(pg_db):
    """
    Creates two distinct merchants (A & B) with users and roles:
    - User A: OWNER of Merchant A
    - User B: STAFF of Merchant B
    - User Multi: ADMIN of Merchant A, STAFF of Merchant B
    - User Outsider: No merchant membership
    """
    # Merchant A
    merchant_a = Merchant(name="Alpha Grocery", business_type="Retail", status="ACTIVE")
    # Merchant B
    merchant_b = Merchant(name="Beta Electronics", business_type="Electronics", status="ACTIVE")
    pg_db.add_all([merchant_a, merchant_b])
    pg_db.flush()

    # Users
    user_a = User(email=f"owner_a_{uuid.uuid4().hex[:6]}@example.com", is_active=True)
    user_a.set_password("AlphaPassword123!")
    user_b = User(email=f"staff_b_{uuid.uuid4().hex[:6]}@example.com", is_active=True)
    user_b.set_password("BetaPassword123!")
    user_multi = User(email=f"multi_{uuid.uuid4().hex[:6]}@example.com", is_active=True)
    user_multi.set_password("MultiPassword123!")
    user_outsider = User(email=f"outsider_{uuid.uuid4().hex[:6]}@example.com", is_active=True)
    user_outsider.set_password("OutsiderPassword123!")

    pg_db.add_all([user_a, user_b, user_multi, user_outsider])
    pg_db.flush()

    # Memberships
    # User A -> OWNER of Merchant A
    m_user_a = MerchantUser(merchant_id=merchant_a.id, user_id=user_a.id, role="OWNER")
    # User B -> STAFF of Merchant B
    m_user_b = MerchantUser(merchant_id=merchant_b.id, user_id=user_b.id, role="STAFF")
    # User Multi -> ADMIN of Merchant A, STAFF of Merchant B
    m_user_multi_a = MerchantUser(merchant_id=merchant_a.id, user_id=user_multi.id, role="ADMIN")
    m_user_multi_b = MerchantUser(merchant_id=merchant_b.id, user_id=user_multi.id, role="STAFF")

    pg_db.add_all([m_user_a, m_user_b, m_user_multi_a, m_user_multi_b])
    pg_db.commit()

    return {
        "merchant_a": merchant_a,
        "merchant_b": merchant_b,
        "user_a": user_a,
        "user_b": user_b,
        "user_multi": user_multi,
        "user_outsider": user_outsider,
    }


def auth_header(user: User) -> dict:
    """Helper returning Bearer Authorization header for user."""
    token = create_access_token(user_id=user.id, email=user.email)
    return {"Authorization": f"Bearer {token}"}


# =====================================================================
# 1. Merchant Context Resolution Tests
# =====================================================================

def test_authenticated_user_resolves_belonging_merchant(pg_client, setup_two_merchants):
    """1. User belonging to Merchant A can resolve merchant context."""
    user_a = setup_two_merchants["user_a"]
    merchant_a = setup_two_merchants["merchant_a"]

    res = pg_client.get(
        "/api/v1/merchants/context",
        headers={**auth_header(user_a), "X-Merchant-ID": str(merchant_a.id)},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == str(merchant_a.id)
    assert data["name"] == merchant_a.name
    assert data["user_role"] == "OWNER"


def test_authenticated_user_cannot_resolve_unauthorized_merchant(pg_client, setup_two_merchants):
    """2. User A cannot resolve context for Merchant B (cross-tenant rejection)."""
    user_a = setup_two_merchants["user_a"]
    merchant_b = setup_two_merchants["merchant_b"]

    res = pg_client.get(
        "/api/v1/merchants/context",
        headers={**auth_header(user_a), "X-Merchant-ID": str(merchant_b.id)},
    )
    assert res.status_code == 403
    assert "not a member" in res.json()["detail"].lower()


def test_unauthenticated_user_cannot_resolve_merchant_context(pg_client):
    """3. Unauthenticated request returns 401."""
    res = pg_client.get("/api/v1/merchants/context")
    assert res.status_code == 401


def test_arbitrary_merchant_uuid_cannot_bypass_membership(pg_client, setup_two_merchants):
    """4. Supplying a fabricated UUID in X-Merchant-ID returns 403."""
    user_a = setup_two_merchants["user_a"]
    random_uuid = str(uuid.uuid4())

    res = pg_client.get(
        "/api/v1/merchants/context",
        headers={**auth_header(user_a), "X-Merchant-ID": random_uuid},
    )
    assert res.status_code == 403


def test_multi_merchant_user_can_access_each_authorized_merchant(pg_client, setup_two_merchants):
    """5. Multi-merchant user accesses both organizations using explicit context."""
    user_multi = setup_two_merchants["user_multi"]
    merchant_a = setup_two_merchants["merchant_a"]
    merchant_b = setup_two_merchants["merchant_b"]

    # Access Merchant A as ADMIN
    res_a = pg_client.get(
        "/api/v1/merchants/context",
        headers={**auth_header(user_multi), "X-Merchant-ID": str(merchant_a.id)},
    )
    assert res_a.status_code == 200
    assert res_a.json()["id"] == str(merchant_a.id)
    assert res_a.json()["user_role"] == "ADMIN"

    # Access Merchant B as STAFF
    res_b = pg_client.get(
        "/api/v1/merchants/context",
        headers={**auth_header(user_multi), "X-Merchant-ID": str(merchant_b.id)},
    )
    assert res_b.status_code == 200
    assert res_b.json()["id"] == str(merchant_b.id)
    assert res_b.json()["user_role"] == "STAFF"


def test_multi_merchant_user_omitting_merchant_id_returns_400(pg_client, setup_two_merchants):
    """User with multiple memberships must specify which merchant context to act on."""
    user_multi = setup_two_merchants["user_multi"]
    res = pg_client.get("/api/v1/merchants/context", headers=auth_header(user_multi))
    assert res.status_code == 400
    assert "multiple merchant memberships" in res.json()["detail"].lower()


def test_outsider_user_belonging_to_zero_merchants_returns_403(pg_client, setup_two_merchants):
    """User with no memberships cannot resolve any merchant context."""
    user_outsider = setup_two_merchants["user_outsider"]
    res = pg_client.get("/api/v1/merchants/context", headers=auth_header(user_outsider))
    assert res.status_code == 403


def test_merchant_context_does_not_trust_client_supplied_role(pg_client, setup_two_merchants):
    """6 & 25. Attempting to spoof role via headers or query parameters is completely ignored."""
    user_b = setup_two_merchants["user_b"]
    merchant_b = setup_two_merchants["merchant_b"]

    res = pg_client.get(
        "/api/v1/merchants/context?role=OWNER",
        headers={
            **auth_header(user_b),
            "X-Merchant-ID": str(merchant_b.id),
            "X-Role": "OWNER",
        },
    )
    assert res.status_code == 200
    # Role is strictly read from PostgreSQL MerchantUser (STAFF), never from client!
    assert res.json()["user_role"] == "STAFF"


# =====================================================================
# 2. Role-Based Access Control (RBAC) Tests
# =====================================================================

def test_owner_can_access_owner_endpoint(pg_client, setup_two_merchants):
    """7. OWNER can access OWNER-only endpoint."""
    user_a = setup_two_merchants["user_a"]
    merchant_a = setup_two_merchants["merchant_a"]

    res = pg_client.get(
        "/api/v1/merchants/owner-only",
        headers={**auth_header(user_a), "X-Merchant-ID": str(merchant_a.id)},
    )
    assert res.status_code == 200
    assert res.json()["role"] == "OWNER"


def test_admin_can_access_admin_endpoint(pg_client, setup_two_merchants):
    """8. ADMIN can access ADMIN-authorized endpoint."""
    user_multi = setup_two_merchants["user_multi"]
    merchant_a = setup_two_merchants["merchant_a"]

    res = pg_client.get(
        "/api/v1/merchants/admin-only",
        headers={**auth_header(user_multi), "X-Merchant-ID": str(merchant_a.id)},
    )
    assert res.status_code == 200
    assert res.json()["role"] == "ADMIN"


def test_staff_can_access_staff_endpoint(pg_client, setup_two_merchants):
    """9. STAFF can access STAFF-authorized endpoint."""
    user_b = setup_two_merchants["user_b"]
    merchant_b = setup_two_merchants["merchant_b"]

    res = pg_client.get(
        "/api/v1/merchants/staff-accessible",
        headers={**auth_header(user_b), "X-Merchant-ID": str(merchant_b.id)},
    )
    assert res.status_code == 200
    assert res.json()["role"] == "STAFF"


def test_staff_cannot_access_owner_only_endpoint(pg_client, setup_two_merchants):
    """10. STAFF cannot access OWNER-only endpoint."""
    user_b = setup_two_merchants["user_b"]
    merchant_b = setup_two_merchants["merchant_b"]

    res = pg_client.get(
        "/api/v1/merchants/owner-only",
        headers={**auth_header(user_b), "X-Merchant-ID": str(merchant_b.id)},
    )
    assert res.status_code == 403
    assert "insufficient role permissions" in res.json()["detail"].lower()


def test_staff_cannot_access_admin_only_endpoint(pg_client, setup_two_merchants):
    """11. STAFF cannot access ADMIN-only endpoint."""
    user_b = setup_two_merchants["user_b"]
    merchant_b = setup_two_merchants["merchant_b"]

    res = pg_client.get(
        "/api/v1/merchants/admin-only",
        headers={**auth_header(user_b), "X-Merchant-ID": str(merchant_b.id)},
    )
    assert res.status_code == 403


def test_admin_cannot_access_owner_only_endpoint(pg_client, setup_two_merchants):
    """12. ADMIN cannot access OWNER-only endpoint."""
    user_multi = setup_two_merchants["user_multi"]
    merchant_a = setup_two_merchants["merchant_a"]

    res = pg_client.get(
        "/api/v1/merchants/owner-only",
        headers={**auth_header(user_multi), "X-Merchant-ID": str(merchant_a.id)},
    )
    assert res.status_code == 403


def test_inactive_merchant_organization_is_rejected(pg_client, pg_db, setup_two_merchants):
    """26. Deactivated or suspended merchant rejects access even for OWNER."""
    user_a = setup_two_merchants["user_a"]
    merchant_a = setup_two_merchants["merchant_a"]
    merchant_a.status = "SUSPENDED"
    pg_db.commit()

    res = pg_client.get(
        "/api/v1/merchants/context",
        headers={**auth_header(user_a), "X-Merchant-ID": str(merchant_a.id)},
    )
    assert res.status_code == 403
    assert "not active" in res.json()["detail"].lower()


# =====================================================================
# 3. Tenant Isolation & IDOR Tests Across Canonical Models
# =====================================================================

def test_merchant_a_user_cannot_access_merchant_b_payments(pg_client, pg_db, setup_two_merchants):
    """15 & 21. Merchant A user cannot access Merchant B Payment even with known UUID."""
    user_a = setup_two_merchants["user_a"]
    merchant_a = setup_two_merchants["merchant_a"]
    merchant_b = setup_two_merchants["merchant_b"]

    # Create Payment in Merchant B
    payment_b = Payment(
        merchant_id=merchant_b.id,
        amount_minor=75000,
        currency="INR",
        provider="RAZORPAY",
        provider_payment_id=f"pay_b_{uuid.uuid4().hex[:8]}",
        status=PaymentStatus.CAPTURED.value,
    )
    pg_db.add(payment_b)
    pg_db.commit()

    # User A requests Payment B under Merchant A context
    res = pg_client.get(
        f"/api/v1/merchants/payments/{payment_b.id}",
        headers={**auth_header(user_a), "X-Merchant-ID": str(merchant_a.id)},
    )
    assert res.status_code == 404

    # Direct service layer query-level isolation check
    scoped_result = tenant_service.get_payment_for_merchant(
        db=pg_db,
        payment_id=payment_b.id,
        merchant_id=merchant_a.id,
    )
    assert scoped_result is None


def test_merchant_a_user_cannot_access_merchant_b_payment_events(pg_db, setup_two_merchants):
    """16. Direct service check: PaymentEvent query is scoped to merchant."""
    merchant_a = setup_two_merchants["merchant_a"]
    merchant_b = setup_two_merchants["merchant_b"]

    event_b = PaymentEvent(
        merchant_id=merchant_b.id,
        provider="RAZORPAY",
        event_id=f"evt_{uuid.uuid4().hex[:8]}",
        event_type="payment.captured",
        payload_hash="testhash123",
        processing_status=EventProcessingStatus.RECEIVED.value,
    )
    pg_db.add(event_b)
    pg_db.commit()

    # Querying event_b with merchant_a must return None
    assert tenant_service.get_payment_event_for_merchant(pg_db, event_b.id, merchant_a.id) is None
    # Querying event_b with merchant_b succeeds
    assert tenant_service.get_payment_event_for_merchant(pg_db, event_b.id, merchant_b.id) is not None


def test_merchant_a_user_cannot_access_merchant_b_devices(pg_client, pg_db, setup_two_merchants):
    """17. Merchant A user cannot access Merchant B Device."""
    user_a = setup_two_merchants["user_a"]
    merchant_a = setup_two_merchants["merchant_a"]
    merchant_b = setup_two_merchants["merchant_b"]

    device_b = Device(
        merchant_id=merchant_b.id,
        device_type=DeviceType.SOUNDBOX.value,
        device_name=f"SB-{uuid.uuid4().hex[:8]}",
        status=DeviceStatus.ACTIVE.value,
    )
    pg_db.add(device_b)
    pg_db.commit()

    res = pg_client.get(
        f"/api/v1/merchants/devices/{device_b.id}",
        headers={**auth_header(user_a), "X-Merchant-ID": str(merchant_a.id)},
    )
    assert res.status_code == 404


def test_merchant_a_user_cannot_access_merchant_b_device_sessions(pg_client, pg_db, setup_two_merchants):
    """18. Indirect tenancy: DeviceSession -> Device -> Merchant is strictly enforced."""
    user_a = setup_two_merchants["user_a"]
    merchant_a = setup_two_merchants["merchant_a"]
    merchant_b = setup_two_merchants["merchant_b"]

    device_b = Device(
        merchant_id=merchant_b.id,
        device_type=DeviceType.SOUNDBOX.value,
        device_name=f"SB-SESS-{uuid.uuid4().hex[:8]}",
        status=DeviceStatus.ACTIVE.value,
    )
    pg_db.add(device_b)
    pg_db.flush()

    session_b = DeviceSession(
        device_id=device_b.id,
        session_token_hash=f"session_hash_{uuid.uuid4().hex}",
        status=DeviceSessionStatus.CONNECTED.value,
        expires_at=datetime.now(timezone.utc),
    )
    pg_db.add(session_b)
    pg_db.commit()

    # User A attempts to access DeviceSession of Merchant B
    res = pg_client.get(
        f"/api/v1/merchants/device-sessions/{session_b.id}",
        headers={**auth_header(user_a), "X-Merchant-ID": str(merchant_a.id)},
    )
    assert res.status_code == 404


def test_merchant_a_user_cannot_access_merchant_b_voice_notifications(pg_db, setup_two_merchants):
    """19. VoiceNotification query is strictly tenant-scoped."""
    merchant_a = setup_two_merchants["merchant_a"]
    merchant_b = setup_two_merchants["merchant_b"]

    device_b = Device(
        merchant_id=merchant_b.id,
        device_type=DeviceType.SOUNDBOX.value,
        device_name=f"SB-NOTIF-{uuid.uuid4().hex[:8]}",
        status=DeviceStatus.ACTIVE.value,
    )
    payment_b = Payment(
        merchant_id=merchant_b.id,
        amount_minor=50000,
        currency="INR",
        provider="RAZORPAY",
        provider_payment_id=f"pay_notif_{uuid.uuid4().hex[:8]}",
        status=PaymentStatus.CAPTURED.value,
    )
    pg_db.add_all([device_b, payment_b])
    pg_db.flush()

    notif_b = VoiceNotification(
        merchant_id=merchant_b.id,
        device_id=device_b.id,
        payment_id=payment_b.id,
        message="INR 500 received",
        status=VoiceNotificationStatus.PENDING.value,
    )
    pg_db.add(notif_b)
    pg_db.commit()

    assert tenant_service.get_voice_notification_for_merchant(pg_db, notif_b.id, merchant_a.id) is None
    assert tenant_service.get_voice_notification_for_merchant(pg_db, notif_b.id, merchant_b.id) is not None


def test_merchant_a_user_cannot_access_merchant_b_provider_connections(pg_db, setup_two_merchants):
    """20. ProviderConnection query is strictly tenant-scoped."""
    merchant_a = setup_two_merchants["merchant_a"]
    merchant_b = setup_two_merchants["merchant_b"]

    conn_b = ProviderConnection(
        merchant_id=merchant_b.id,
        provider="RAZORPAY",
        provider_account_reference=f"acc_{uuid.uuid4().hex[:8]}",
    )
    pg_db.add(conn_b)
    pg_db.commit()

    assert tenant_service.get_provider_connection_for_merchant(pg_db, conn_b.id, merchant_a.id) is None
    assert tenant_service.get_provider_connection_for_merchant(pg_db, conn_b.id, merchant_b.id) is not None


def test_changing_merchant_id_in_request_cannot_bypass_authorization(pg_client, setup_two_merchants):
    """22 & 24. User A supplying X-Merchant-ID: Merchant B is blocked with 403."""
    user_a = setup_two_merchants["user_a"]
    merchant_b = setup_two_merchants["merchant_b"]

    res = pg_client.get(
        "/api/v1/merchants/context",
        headers={**auth_header(user_a), "X-Merchant-ID": str(merchant_b.id)},
    )
    assert res.status_code == 403


def test_authorization_failures_do_not_expose_database_details(pg_client, setup_two_merchants):
    """27 & 28. Error payloads contain sanitized messages, no SQL or schema leaks."""
    user_a = setup_two_merchants["user_a"]
    fake_merchant = str(uuid.uuid4())

    res = pg_client.get(
        "/api/v1/merchants/context",
        headers={**auth_header(user_a), "X-Merchant-ID": fake_merchant},
    )
    assert res.status_code == 403
    text = res.text
    assert "PostgreSQL" not in text
    assert "SELECT" not in text
    assert "merchant_users" not in text
    assert "Traceback" not in text


def test_explicit_role_sets_and_unknown_role_rejected(pg_client, pg_db, setup_two_merchants):
    """13 & 14. Explicit role sets work correctly; unknown or invalid roles are rejected."""
    user_a = setup_two_merchants["user_a"]
    merchant_a = setup_two_merchants["merchant_a"]

    # Temporarily set role to an unknown/invalid role
    membership = pg_db.query(MerchantUser).filter(
        MerchantUser.user_id == user_a.id,
        MerchantUser.merchant_id == merchant_a.id,
    ).first()
    membership.role = "UNKNOWN_ROLE"
    pg_db.commit()

    # Any endpoint checking standard roles rejects
    res_owner = pg_client.get(
        "/api/v1/merchants/owner-only",
        headers={**auth_header(user_a), "X-Merchant-ID": str(merchant_a.id)},
    )
    assert res_owner.status_code == 403

    res_staff = pg_client.get(
        "/api/v1/merchants/staff-accessible",
        headers={**auth_header(user_a), "X-Merchant-ID": str(merchant_a.id)},
    )
    assert res_staff.status_code == 403


def test_changing_resource_id_cannot_bypass_tenant_checks(pg_client, pg_db, setup_two_merchants):
    """23. Iterating or changing resource IDs cannot bypass tenant isolation."""
    user_a = setup_two_merchants["user_a"]
    merchant_a = setup_two_merchants["merchant_a"]
    merchant_b = setup_two_merchants["merchant_b"]

    payment_b1 = Payment(
        merchant_id=merchant_b.id,
        amount_minor=1000,
        currency="INR",
        provider="RAZORPAY",
        provider_payment_id=f"pay_seq1_{uuid.uuid4().hex[:8]}",
        status=PaymentStatus.CAPTURED.value,
    )
    payment_b2 = Payment(
        merchant_id=merchant_b.id,
        amount_minor=2000,
        currency="INR",
        provider="RAZORPAY",
        provider_payment_id=f"pay_seq2_{uuid.uuid4().hex[:8]}",
        status=PaymentStatus.CAPTURED.value,
    )
    pg_db.add_all([payment_b1, payment_b2])
    pg_db.commit()

    for p in [payment_b1, payment_b2]:
        res = pg_client.get(
            f"/api/v1/merchants/payments/{p.id}",
            headers={**auth_header(user_a), "X-Merchant-ID": str(merchant_a.id)},
        )
        assert res.status_code == 404


def test_valid_jwt_from_merchant_a_cannot_access_merchant_b(pg_client, setup_two_merchants):
    """24. Valid JWT from Merchant A user cannot access Merchant B routes."""
    user_a = setup_two_merchants["user_a"]
    merchant_b = setup_two_merchants["merchant_b"]

    # Even with a perfectly valid access token, accessing Merchant B returns 403
    res = pg_client.get(
        "/api/v1/merchants/owner-only",
        headers={**auth_header(user_a), "X-Merchant-ID": str(merchant_b.id)},
    )
    assert res.status_code == 403
    assert "not a member" in res.json()["detail"].lower()


def test_client_supplied_merchant_id_cannot_bypass_membership(pg_client, setup_two_merchants):
    """26. Client-supplied merchant ID cannot bypass server-side membership check."""
    user_a = setup_two_merchants["user_a"]
    merchant_b = setup_two_merchants["merchant_b"]

    # Header spoofing attempt
    res = pg_client.get(
        "/api/v1/merchants/staff-accessible",
        headers={**auth_header(user_a), "X-Merchant-ID": str(merchant_b.id)},
    )
    assert res.status_code == 403


def test_authorization_failures_do_not_expose_unrelated_merchant_information(pg_client, setup_two_merchants):
    """28. Authorization failures never leak name, business type, or data of the target merchant."""
    user_a = setup_two_merchants["user_a"]
    merchant_b = setup_two_merchants["merchant_b"]

    res = pg_client.get(
        "/api/v1/merchants/context",
        headers={**auth_header(user_a), "X-Merchant-ID": str(merchant_b.id)},
    )
    assert res.status_code == 403
    assert merchant_b.name not in res.text
    assert merchant_b.business_type not in res.text
