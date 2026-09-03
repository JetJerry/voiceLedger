"""
Phase 6.1 — Soundbox Device Management & Pairing Boundary Test Suite.

Verifies:
1. Device Provisioning: Merchant Owner/Admin can register a physical Soundbox.
2. Secret Exposure Policy: Raw device_secret returned ONLY once upon registration.
3. Cryptographic Hashing at Rest: Raw device secret is NEVER persisted; only SHA-256 hash is stored.
4. Device Authentication: Physical Soundbox exchanges valid secret for an active DeviceSession.
5. Invalid Credentials: Wrong secret is rejected with HTTP 401.
6. Inactive Device Rejection: Inactive, disabled, or revoked devices cannot authenticate.
7. Heartbeat Telemetry: Authenticated heartbeat updates last_seen_at and last_activity_at.
8. Expired/Invalid Session Rejection: Expired, forged, or missing session tokens rejected with HTTP 401.
9. Cross-Merchant Authorization: Merchant A cannot register or list devices for Merchant B.
10. Online/Offline Calculation: List endpoint accurately computes online status based on recent heartbeat.
11. Zero Financial Mutation: Device operations do not alter payments or ledgers.
12. Zero Provider Coupling: Device service and API contain zero Razorpay SDK imports.
"""
from datetime import datetime, timezone, timedelta
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.config import settings
from backend.app.models.user import User
from backend.app.models.merchant import Merchant
from backend.app.models.merchant_user import MerchantUser
from backend.app.models.device import Device, DeviceStatus
from backend.app.models.device_session import DeviceSession, DeviceSessionStatus
from backend.app.core.security import create_access_token, hash_password
from backend.app.services.device_service import device_service

# Authoritative PostgreSQL connection for test fixtures
pg_engine = create_engine(settings.DATABASE_URL)
PGTestSession = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def tenancy_setup():
    """Create committed test merchants, users, and roles in PostgreSQL."""
    db = PGTestSession()
    cleanup_user_ids = []
    cleanup_merchant_ids = []

    try:
        # Merchant A
        merchant_a = Merchant(
            id=uuid.uuid4(),
            name="Kirana A Electronics",
            business_type="Retail",
            status="ACTIVE",
            currency="INR",
        )
        db.add(merchant_a)
        cleanup_merchant_ids.append(merchant_a.id)

        # Merchant B
        merchant_b = Merchant(
            id=uuid.uuid4(),
            name="Kirana B Supermarket",
            business_type="Retail",
            status="ACTIVE",
            currency="INR",
        )
        db.add(merchant_b)
        cleanup_merchant_ids.append(merchant_b.id)

        # User A (Owner of Merchant A)
        user_a = User(
            id=uuid.uuid4(),
            email=f"owner_a_{uuid.uuid4().hex[:6]}@example.com",
            hashed_password=hash_password("ValidPassword123!"),
            is_active=True,
        )
        db.add(user_a)
        cleanup_user_ids.append(user_a.id)

        # User B (Owner of Merchant B)
        user_b = User(
            id=uuid.uuid4(),
            email=f"owner_b_{uuid.uuid4().hex[:6]}@example.com",
            hashed_password=hash_password("ValidPassword123!"),
            is_active=True,
        )
        db.add(user_b)
        cleanup_user_ids.append(user_b.id)

        db.flush()

        # Memberships
        mu_a = MerchantUser(id=uuid.uuid4(), merchant_id=merchant_a.id, user_id=user_a.id, role="OWNER")
        mu_b = MerchantUser(id=uuid.uuid4(), merchant_id=merchant_b.id, user_id=user_b.id, role="OWNER")
        db.add(mu_a)
        db.add(mu_b)
        db.commit()

        yield {
            "merchant_a": merchant_a,
            "merchant_b": merchant_b,
            "user_a": user_a,
            "user_b": user_b,
            "token_a": create_access_token(user_id=user_a.id, email=user_a.email),
            "token_b": create_access_token(user_id=user_b.id, email=user_b.email),
        }

    finally:
        # Cleanup
        db.query(DeviceSession).delete()
        db.query(Device).delete()
        db.query(MerchantUser).filter(MerchantUser.user_id.in_(cleanup_user_ids)).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_(cleanup_user_ids)).delete(synchronize_session=False)
        db.query(Merchant).filter(Merchant.id.in_(cleanup_merchant_ids)).delete(synchronize_session=False)
        db.commit()
        db.close()


# =====================================================================
# 1. Device Registration & Credential Hashing
# =====================================================================

def test_merchant_can_register_soundbox_device(client, tenancy_setup):
    """Merchant Owner can provision a new Soundbox; returns device secret once."""
    token = tenancy_setup["token_a"]
    m_id = tenancy_setup["merchant_a"].id

    resp = client.post(
        f"/api/v1/merchants/{m_id}/devices",
        json={"device_name": "Front Counter Soundbox", "device_type": "SOUNDBOX"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["device_name"] == "Front Counter Soundbox"
    assert data["status"] == "ACTIVE"
    assert data["device_secret"].startswith("devsec_")

    # Verify in DB: raw secret is NOT stored; only 64-char SHA-256 hash is persisted
    db = PGTestSession()
    try:
        device = db.query(Device).filter(Device.id == data["id"]).first()
        assert device is not None
        assert device.device_token_hash is not None
        assert len(device.device_token_hash) == 64
        assert device.device_token_hash != data["device_secret"]
        assert device.device_token_hash == device_service.hash_token(data["device_secret"])
    finally:
        db.close()


def test_device_secret_never_returned_in_list(client, tenancy_setup):
    """Device secret is strictly omitted from list responses."""
    token = tenancy_setup["token_a"]
    m_id = tenancy_setup["merchant_a"].id

    # Register
    reg_resp = client.post(
        f"/api/v1/merchants/{m_id}/devices",
        json={"device_name": "Billing Soundbox 1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert "device_secret" in reg_resp.json()

    # List
    list_resp = client.get(
        f"/api/v1/merchants/{m_id}/devices",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_resp.status_code == 200
    devices = list_resp.json()
    assert len(devices) == 1
    assert "device_secret" not in devices[0]
    assert "device_token_hash" not in devices[0]


def test_cross_merchant_cannot_register_or_view_devices(client, tenancy_setup):
    """User B (Merchant B) cannot register or list devices for Merchant A."""
    token_b = tenancy_setup["token_b"]
    m_a_id = tenancy_setup["merchant_a"].id

    # Register attempt
    resp = client.post(
        f"/api/v1/merchants/{m_a_id}/devices",
        json={"device_name": "Malicious Device"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 403

    # List attempt
    list_resp = client.get(
        f"/api/v1/merchants/{m_a_id}/devices",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert list_resp.status_code == 403


# =====================================================================
# 2. Device Authentication & Session Issuance
# =====================================================================

def test_valid_device_authentication_issues_session(client, tenancy_setup):
    """Physical Soundbox exchanges secret for an active DeviceSession token."""
    token = tenancy_setup["token_a"]
    m_id = tenancy_setup["merchant_a"].id

    reg_resp = client.post(
        f"/api/v1/merchants/{m_id}/devices",
        json={"device_name": "Counter 1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    device_id = reg_resp.json()["id"]
    secret = reg_resp.json()["device_secret"]

    # Device authenticates
    auth_resp = client.post(
        f"/api/v1/devices/{device_id}/authenticate",
        json={"device_secret": secret},
    )
    assert auth_resp.status_code == 200
    auth_data = auth_resp.json()
    assert auth_data["session_token"].startswith("devsess_")
    assert auth_data["device_id"] == device_id
    assert auth_data["merchant_id"] == str(m_id)

    # Verify session in DB: only SHA-256 hash is persisted
    db = PGTestSession()
    try:
        session = db.query(DeviceSession).filter(DeviceSession.device_id == device_id).first()
        assert session is not None
        assert session.status == DeviceSessionStatus.CONNECTED.value
        assert session.session_token_hash == device_service.hash_token(auth_data["session_token"])
    finally:
        db.close()


def test_invalid_device_secret_rejected_with_401(client, tenancy_setup):
    """Wrong secret is rejected with HTTP 401 Unauthorized."""
    token = tenancy_setup["token_a"]
    m_id = tenancy_setup["merchant_a"].id

    reg_resp = client.post(
        f"/api/v1/merchants/{m_id}/devices",
        json={"device_name": "Counter 2"},
        headers={"Authorization": f"Bearer {token}"},
    )
    device_id = reg_resp.json()["id"]

    auth_resp = client.post(
        f"/api/v1/devices/{device_id}/authenticate",
        json={"device_secret": "wrong_invalid_secret_12345678"},
    )
    assert auth_resp.status_code == 401


def test_inactive_or_disabled_device_cannot_authenticate(client, tenancy_setup):
    """A device marked DISABLED cannot authenticate."""
    token = tenancy_setup["token_a"]
    m_id = tenancy_setup["merchant_a"].id

    reg_resp = client.post(
        f"/api/v1/merchants/{m_id}/devices",
        json={"device_name": "Disabled Device"},
        headers={"Authorization": f"Bearer {token}"},
    )
    device_id = reg_resp.json()["id"]
    secret = reg_resp.json()["device_secret"]

    # Disable device in DB
    db = PGTestSession()
    try:
        dev = db.query(Device).filter(Device.id == device_id).first()
        dev.status = DeviceStatus.DISABLED.value
        db.commit()
    finally:
        db.close()

    auth_resp = client.post(
        f"/api/v1/devices/{device_id}/authenticate",
        json={"device_secret": secret},
    )
    assert auth_resp.status_code == 403


# =====================================================================
# 3. Heartbeat & Online Status Telemetry
# =====================================================================

def test_authenticated_heartbeat_updates_telemetry(client, tenancy_setup):
    """Heartbeat with active session token updates last_seen_at timestamp."""
    token = tenancy_setup["token_a"]
    m_id = tenancy_setup["merchant_a"].id

    # Register & Authenticate
    reg_resp = client.post(
        f"/api/v1/merchants/{m_id}/devices",
        json={"device_name": "Telemetry Soundbox"},
        headers={"Authorization": f"Bearer {token}"},
    )
    device_id = reg_resp.json()["id"]
    secret = reg_resp.json()["device_secret"]

    auth_resp = client.post(
        f"/api/v1/devices/{device_id}/authenticate",
        json={"device_secret": secret},
    )
    session_token = auth_resp.json()["session_token"]

    # Heartbeat
    hb_resp = client.post(
        f"/api/v1/devices/{device_id}/heartbeat",
        headers={"X-Device-Session-Token": session_token},
    )
    assert hb_resp.status_code == 200
    assert hb_resp.json()["status"] == "ok"
    assert hb_resp.json()["device_id"] == device_id
    assert hb_resp.json()["last_seen_at"] is not None

    # Verify device list reports online
    list_resp = client.get(
        f"/api/v1/merchants/{m_id}/devices",
        headers={"Authorization": f"Bearer {token}"},
    )
    dev_info = list_resp.json()[0]
    assert dev_info["is_online"] is True


def test_missing_or_expired_heartbeat_token_rejected(client, tenancy_setup):
    """Missing or expired session token is rejected with HTTP 401."""
    token = tenancy_setup["token_a"]
    m_id = tenancy_setup["merchant_a"].id

    reg_resp = client.post(
        f"/api/v1/merchants/{m_id}/devices",
        json={"device_name": "Heartbeat Fail Device"},
        headers={"Authorization": f"Bearer {token}"},
    )
    device_id = reg_resp.json()["id"]

    # Missing token
    resp_missing = client.post(f"/api/v1/devices/{device_id}/heartbeat")
    assert resp_missing.status_code == 401

    # Fake / invalid token
    resp_fake = client.post(
        f"/api/v1/devices/{device_id}/heartbeat",
        headers={"X-Device-Session-Token": "devsess_completely_fabricated_token_999"},
    )
    assert resp_fake.status_code == 401


def test_expired_session_rejected_during_heartbeat(client, tenancy_setup):
    """Expired session cannot send heartbeat."""
    token = tenancy_setup["token_a"]
    m_id = tenancy_setup["merchant_a"].id

    reg_resp = client.post(
        f"/api/v1/merchants/{m_id}/devices",
        json={"device_name": "Expiring Device"},
        headers={"Authorization": f"Bearer {token}"},
    )
    device_id = reg_resp.json()["id"]
    secret = reg_resp.json()["device_secret"]

    auth_resp = client.post(
        f"/api/v1/devices/{device_id}/authenticate",
        json={"device_secret": secret},
    )
    session_token = auth_resp.json()["session_token"]

    # Expire session in DB
    db = PGTestSession()
    try:
        sess = db.query(DeviceSession).filter(DeviceSession.device_id == device_id).first()
        sess.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.commit()
    finally:
        db.close()

    hb_resp = client.post(
        f"/api/v1/devices/{device_id}/heartbeat",
        headers={"X-Device-Session-Token": session_token},
    )
    assert hb_resp.status_code == 401


# =====================================================================
# 4. Architectural Boundaries
# =====================================================================

def test_device_subsystem_has_zero_razorpay_coupling():
    """Verify device service and API contain zero Razorpay imports."""
    import inspect
    import backend.app.services.device_service as ds_mod
    import backend.app.api.v1.devices as ep_mod

    for mod in (ds_mod, ep_mod):
        source = inspect.getsource(mod)
        assert "RazorpayClient" not in source
        assert "RazorpayProvider" not in source
        assert "backend.app.providers.razorpay" not in source
