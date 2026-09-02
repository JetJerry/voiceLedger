import uuid
from datetime import datetime, timezone, timedelta
import secrets
import pytest
import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.config import Settings, settings
from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.models.merchant import Merchant
from backend.app.models.merchant_user import MerchantUser
from backend.app.models.user_session import UserSession
from backend.app.models.payment import Payment, PaymentStatus
from backend.app.models.payment_event import PaymentEvent, EventProcessingStatus
from backend.app.models.device import Device, DeviceStatus, DeviceType
from backend.app.models.device_session import DeviceSession, DeviceSessionStatus
from backend.app.models.voice_notification import VoiceNotification, VoiceNotificationStatus
from backend.app.models.provider_connection import ProviderConnection
from backend.app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_token,
    sanitize_sensitive_data,
    InvalidTokenError,
    TokenExpiredError,
    TokenReuseError,
)
from backend.app.services.tenant_service import (
    tenant_service,
    CrossTenantAccessError,
)

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
def setup_security_merchants(pg_db):
    """Creates two distinct merchants with Users and memberships."""
    m_alpha = Merchant(name="Hardened Alpha", status="ACTIVE")
    m_beta = Merchant(name="Hardened Beta", status="ACTIVE")
    pg_db.add_all([m_alpha, m_beta])
    pg_db.flush()

    user_owner = User(email=f"owner_{uuid.uuid4().hex[:6]}@example.com", is_active=True)
    user_owner.set_password("SecurePassword123!")
    user_staff = User(email=f"staff_{uuid.uuid4().hex[:6]}@example.com", is_active=True)
    user_staff.set_password("SecurePassword123!")
    user_admin = User(email=f"admin_{uuid.uuid4().hex[:6]}@example.com", is_active=True)
    user_admin.set_password("SecurePassword123!")
    user_inactive = User(email=f"inactive_{uuid.uuid4().hex[:6]}@example.com", is_active=False)
    user_inactive.set_password("SecurePassword123!")

    pg_db.add_all([user_owner, user_staff, user_admin, user_inactive])
    pg_db.flush()

    # M_alpha memberships
    pg_db.add(MerchantUser(merchant_id=m_alpha.id, user_id=user_owner.id, role="OWNER"))
    pg_db.add(MerchantUser(merchant_id=m_alpha.id, user_id=user_admin.id, role="ADMIN"))
    pg_db.add(MerchantUser(merchant_id=m_alpha.id, user_id=user_staff.id, role="STAFF"))

    # M_beta membership
    user_beta_owner = User(email=f"beta_owner_{uuid.uuid4().hex[:6]}@example.com", is_active=True)
    user_beta_owner.set_password("BetaPassword123!")
    pg_db.add(user_beta_owner)
    pg_db.flush()
    pg_db.add(MerchantUser(merchant_id=m_beta.id, user_id=user_beta_owner.id, role="OWNER"))

    pg_db.commit()

    return {
        "m_alpha": m_alpha,
        "m_beta": m_beta,
        "user_owner": user_owner,
        "user_admin": user_admin,
        "user_staff": user_staff,
        "user_inactive": user_inactive,
        "user_beta_owner": user_beta_owner,
    }


def auth_header(user: User) -> dict:
    """Helper returning Bearer Authorization header for user."""
    token = create_access_token(user_id=user.id, email=user.email)
    return {"Authorization": f"Bearer {token}"}


# =====================================================================
# 1. JWT Security Hardening Tests (1-10)
# =====================================================================

def test_unsigned_jwt_rejected():
    """1. Unsigned JWT (alg=none) is rejected."""
    payload = {
        "sub": str(uuid.uuid4()),
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int((datetime.now(timezone.utc) + timedelta(minutes=15)).timestamp()),
    }
    # Craft token with alg=none and no signature
    unsigned_token = jwt.encode(payload, key="", algorithm="none")
    with pytest.raises(InvalidTokenError):
        decode_access_token(unsigned_token)


def test_algorithm_confusion_rejected():
    """2. Algorithm confusion attempts (e.g. HS384 / RS256 when HS256 expected) are rejected."""
    payload = {
        "sub": str(uuid.uuid4()),
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int((datetime.now(timezone.utc) + timedelta(minutes=15)).timestamp()),
    }
    # Encode with HS384 instead of configured HS256
    confused_token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS384")
    with pytest.raises(InvalidTokenError):
        decode_access_token(confused_token)


def test_wrong_signing_key_rejected():
    """3. Token signed with wrong secret key is rejected."""
    payload = {
        "sub": str(uuid.uuid4()),
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int((datetime.now(timezone.utc) + timedelta(minutes=15)).timestamp()),
    }
    wrong_key_token = jwt.encode(payload, "completely_wrong_secret_key_1234567890", algorithm="HS256")
    with pytest.raises(InvalidTokenError):
        decode_access_token(wrong_key_token)


def test_wrong_token_type_rejected():
    """4. Token with type != 'access' is rejected."""
    payload = {
        "sub": str(uuid.uuid4()),
        "type": "refresh",
        "jti": str(uuid.uuid4()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int((datetime.now(timezone.utc) + timedelta(minutes=15)).timestamp()),
    }
    refresh_as_access = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
    with pytest.raises(InvalidTokenError):
        decode_access_token(refresh_as_access)


def test_missing_sub_rejected():
    """5. Token missing 'sub' claim is rejected."""
    payload = {
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int((datetime.now(timezone.utc) + timedelta(minutes=15)).timestamp()),
    }
    no_sub_token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
    with pytest.raises(InvalidTokenError):
        decode_access_token(no_sub_token)


def test_invalid_sub_rejected():
    """6. Token with malformed non-UUID 'sub' claim is rejected."""
    payload = {
        "sub": "not-a-valid-uuid-string",
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int((datetime.now(timezone.utc) + timedelta(minutes=15)).timestamp()),
    }
    invalid_sub_token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
    with pytest.raises(InvalidTokenError):
        decode_access_token(invalid_sub_token)


def test_missing_exp_rejected():
    """7. Token missing 'exp' claim is rejected."""
    payload = {
        "sub": str(uuid.uuid4()),
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
    }
    no_exp_token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
    with pytest.raises(InvalidTokenError):
        decode_access_token(no_exp_token)


def test_expired_token_rejected():
    """8. Expired token is rejected."""
    token = create_access_token(
        user_id=uuid.uuid4(),
        expires_delta=timedelta(seconds=-10),
    )
    with pytest.raises(TokenExpiredError):
        decode_access_token(token)


def test_invalid_claim_structure_rejected():
    """9. Token with invalid/non-numeric iat is rejected safely."""
    payload = {
        "sub": str(uuid.uuid4()),
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": "not_an_int",
        "exp": int((datetime.now(timezone.utc) + timedelta(minutes=15)).timestamp()),
    }
    bad_claim_token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
    with pytest.raises(InvalidTokenError):
        decode_access_token(bad_claim_token)


def test_client_supplied_merchant_role_in_jwt_cannot_grant_authorization(pg_client, setup_security_merchants):
    """10. Attacker-crafted JWT with role claims cannot elevate permissions (PostgreSQL is authoritative)."""
    user_staff = setup_security_merchants["user_staff"]
    m_alpha = setup_security_merchants["m_alpha"]

    # Craft token attempting to inject role=OWNER
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_staff.id),
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=15)).timestamp()),
        "role": "OWNER",
        "is_admin": True,
    }
    spoofed_token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")

    res = pg_client.get(
        "/api/v1/merchants/owner-only",
        headers={"Authorization": f"Bearer {spoofed_token}", "X-Merchant-ID": str(m_alpha.id)},
    )
    # Server checks PostgreSQL MerchantUser (which is STAFF), rejects with 403!
    assert res.status_code == 403


# =====================================================================
# 2. Refresh Token Security Tests (11-18)
# =====================================================================

def test_refresh_token_sufficient_randomness():
    """11. Refresh tokens have high entropy (256-bit) and are globally unique."""
    tokens = {generate_refresh_token() for _ in range(100)}
    assert len(tokens) == 100
    for t in tokens:
        assert len(t) >= 40


def test_plaintext_refresh_token_never_stored(pg_client, pg_db, setup_security_merchants):
    """12. Database stores only 64-char SHA-256 hash, never plaintext token."""
    user = setup_security_merchants["user_owner"]
    login_res = pg_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "SecurePassword123!"},
    )
    assert login_res.status_code == 200
    raw_refresh = login_res.json()["refresh_token"]

    # Inspect PostgreSQL directly
    session = pg_db.query(UserSession).filter(UserSession.user_id == user.id).first()
    assert session is not None
    assert session.token_hash == hash_token(raw_refresh)
    assert raw_refresh != session.token_hash
    assert len(session.token_hash) == 64


def test_rotated_refresh_token_cannot_be_reused(pg_client, setup_security_merchants):
    """13. Presenting an already-rotated refresh token fails with 401."""
    user = setup_security_merchants["user_owner"]
    login_res = pg_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "SecurePassword123!"},
    )
    raw_refresh = login_res.json()["refresh_token"]

    # First rotation succeeds
    rot1_res = pg_client.post("/api/v1/auth/refresh", json={"refresh_token": raw_refresh})
    assert rot1_res.status_code == 200

    # Re-presenting old token fails
    rot2_res = pg_client.post("/api/v1/auth/refresh", json={"refresh_token": raw_refresh})
    assert rot2_res.status_code == 401


def test_refresh_token_reuse_revokes_session_family(pg_client, pg_db, setup_security_merchants):
    """14. Replaying a rotated token revokes the entire session family."""
    user = setup_security_merchants["user_owner"]
    login_res = pg_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "SecurePassword123!"},
    )
    token_1 = login_res.json()["refresh_token"]

    # Rotate to token 2
    rot_res = pg_client.post("/api/v1/auth/refresh", json={"refresh_token": token_1})
    token_2 = rot_res.json()["refresh_token"]

    # Replay token 1 (reuse attack!)
    pg_client.post("/api/v1/auth/refresh", json={"refresh_token": token_1})

    # Assert token 2 was revoked by the reuse detection family revocation
    res_token_2 = pg_client.post("/api/v1/auth/refresh", json={"refresh_token": token_2})
    assert res_token_2.status_code == 401


def test_expired_refresh_token_rejected(pg_client, pg_db, setup_security_merchants):
    """15. Expired refresh token returns 401."""
    user = setup_security_merchants["user_owner"]
    raw_token = generate_refresh_token()
    session = UserSession(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        family_id=uuid.uuid4(),
        is_revoked=False,
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    pg_db.add(session)
    pg_db.commit()

    res = pg_client.post("/api/v1/auth/refresh", json={"refresh_token": raw_token})
    assert res.status_code == 401


def test_revoked_refresh_token_rejected(pg_client, pg_db, setup_security_merchants):
    """16. Manually revoked refresh token returns 401."""
    user = setup_security_merchants["user_owner"]
    raw_token = generate_refresh_token()
    session = UserSession(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        family_id=uuid.uuid4(),
        is_revoked=True,
        revoked_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    pg_db.add(session)
    pg_db.commit()

    res = pg_client.post("/api/v1/auth/refresh", json={"refresh_token": raw_token})
    assert res.status_code == 401


def test_concurrent_refresh_row_locking(pg_db, setup_security_merchants):
    """17. Refresh token rotation uses row locking (with_for_update) to serialize concurrent operations."""
    import inspect
    from backend.app.services.auth_service import AuthService
    source = inspect.getsource(AuthService.rotate_refresh_token)
    assert "with_for_update()" in source


def test_refresh_tokens_never_in_logs_or_errors(pg_client, caplog):
    """18. Refresh tokens never appear in application logs or exception strings."""
    fake_token = "secret_refresh_token_sample_string_12345"
    res = pg_client.post("/api/v1/auth/refresh", json={"refresh_token": fake_token})
    assert res.status_code == 401
    assert fake_token not in res.text
    assert fake_token not in caplog.text


# =====================================================================
# 3. Authentication Security Tests (19-23)
# =====================================================================

def test_password_hash_never_returned(pg_client, setup_security_merchants):
    """19. Responses never contain hashed_password."""
    user = setup_security_merchants["user_owner"]
    res = pg_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "SecurePassword123!"},
    )
    assert res.status_code == 200
    assert "hashed_password" not in res.text
    assert "$argon2id$" not in res.text


def test_password_never_logged(pg_client, caplog):
    """20. Passwords are never logged during authentication."""
    secret_pass = "MySecretPass_998877!"
    pg_client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@example.com", "password": secret_pass},
    )
    assert secret_pass not in caplog.text


def test_login_enumeration_protection(pg_client, setup_security_merchants):
    """21. Unknown user vs bad password return identical generic error messages."""
    user = setup_security_merchants["user_owner"]
    res_wrong_pass = pg_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "WrongPassword123!"},
    )
    res_wrong_user = pg_client.post(
        "/api/v1/auth/login",
        json={"email": "nobody_exists_here_ever@example.com", "password": "WrongPassword123!"},
    )
    assert res_wrong_pass.status_code == 401
    assert res_wrong_user.status_code == 401
    assert res_wrong_pass.json() == res_wrong_user.json()


def test_inactive_user_cannot_authenticate(pg_client, setup_security_merchants):
    """22. Inactive user cannot log in and cannot access protected endpoints."""
    user_inactive = setup_security_merchants["user_inactive"]
    login_res = pg_client.post(
        "/api/v1/auth/login",
        json={"email": user_inactive.email, "password": "SecurePassword123!"},
    )
    assert login_res.status_code == 403

    token = create_access_token(user_id=user_inactive.id, email=user_inactive.email)
    me_res = pg_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 403


def test_invalid_authentication_never_exposes_database_internals(pg_client):
    """23. Malformed authentication input never exposes SQL or database internals."""
    res = pg_client.post(
        "/api/v1/auth/login",
        json={"email": "' OR 1=1; --", "password": "password"},
    )
    assert res.status_code == 401
    assert "syntax error" not in res.text.lower()
    assert "postgresql" not in res.text.lower()


# =====================================================================
# 4. Authorization & Tenant Isolation Tests (24-34)
# =====================================================================

def test_user_cannot_access_merchant_without_membership(pg_client, setup_security_merchants):
    """24. User cannot access merchant without membership."""
    user_staff = setup_security_merchants["user_staff"]
    m_beta = setup_security_merchants["m_beta"]

    res = pg_client.get(
        "/api/v1/merchants/context",
        headers={**auth_header(user_staff), "X-Merchant-ID": str(m_beta.id)},
    )
    assert res.status_code == 403


def test_user_cannot_access_another_merchant_by_changing_id(pg_client, setup_security_merchants):
    """25. Tampering with merchant ID in request is blocked."""
    user_staff = setup_security_merchants["user_staff"]
    fake_merchant = str(uuid.uuid4())

    res = pg_client.get(
        "/api/v1/merchants/context",
        headers={**auth_header(user_staff), "X-Merchant-ID": fake_merchant},
    )
    assert res.status_code == 403


def test_user_cannot_access_another_merchant_payment(pg_client, pg_db, setup_security_merchants):
    """26. User cannot access another merchant's payment."""
    user_owner = setup_security_merchants["user_owner"]
    m_alpha = setup_security_merchants["m_alpha"]
    m_beta = setup_security_merchants["m_beta"]

    p_beta = Payment(
        merchant_id=m_beta.id,
        amount_minor=10000,
        currency="INR",
        provider="RAZORPAY",
        provider_payment_id=f"pay_{uuid.uuid4().hex[:8]}",
        status=PaymentStatus.CAPTURED.value,
    )
    pg_db.add(p_beta)
    pg_db.commit()

    res = pg_client.get(
        f"/api/v1/merchants/payments/{p_beta.id}",
        headers={**auth_header(user_owner), "X-Merchant-ID": str(m_alpha.id)},
    )
    assert res.status_code == 404


def test_user_cannot_access_another_merchant_device(pg_client, pg_db, setup_security_merchants):
    """27. User cannot access another merchant's device."""
    user_owner = setup_security_merchants["user_owner"]
    m_alpha = setup_security_merchants["m_alpha"]
    m_beta = setup_security_merchants["m_beta"]

    d_beta = Device(
        merchant_id=m_beta.id,
        device_type=DeviceType.SOUNDBOX.value,
        device_name="Beta-Box",
        status=DeviceStatus.ACTIVE.value,
    )
    pg_db.add(d_beta)
    pg_db.commit()

    res = pg_client.get(
        f"/api/v1/merchants/devices/{d_beta.id}",
        headers={**auth_header(user_owner), "X-Merchant-ID": str(m_alpha.id)},
    )
    assert res.status_code == 404


def test_user_cannot_access_another_merchant_device_session(pg_client, pg_db, setup_security_merchants):
    """28. User cannot access another merchant's device session."""
    user_owner = setup_security_merchants["user_owner"]
    m_alpha = setup_security_merchants["m_alpha"]
    m_beta = setup_security_merchants["m_beta"]

    d_beta = Device(
        merchant_id=m_beta.id,
        device_type=DeviceType.SOUNDBOX.value,
        device_name="Beta-Box-2",
        status=DeviceStatus.ACTIVE.value,
    )
    pg_db.add(d_beta)
    pg_db.flush()

    s_beta = DeviceSession(
        device_id=d_beta.id,
        session_token_hash=f"hash_{uuid.uuid4().hex}",
        status=DeviceSessionStatus.CONNECTED.value,
        expires_at=datetime.now(timezone.utc),
    )
    pg_db.add(s_beta)
    pg_db.commit()

    res = pg_client.get(
        f"/api/v1/merchants/device-sessions/{s_beta.id}",
        headers={**auth_header(user_owner), "X-Merchant-ID": str(m_alpha.id)},
    )
    assert res.status_code == 404


def test_user_cannot_access_another_merchant_provider_connection(pg_db, setup_security_merchants):
    """29. ProviderConnection is strictly tenant-scoped."""
    m_alpha = setup_security_merchants["m_alpha"]
    m_beta = setup_security_merchants["m_beta"]

    conn_b = ProviderConnection(
        merchant_id=m_beta.id,
        provider="RAZORPAY",
        provider_account_reference="mid_beta",
    )
    pg_db.add(conn_b)
    pg_db.commit()

    assert tenant_service.get_provider_connection_for_merchant(pg_db, conn_b.id, m_alpha.id) is None


def test_user_cannot_access_another_merchant_voice_notification(pg_db, setup_security_merchants):
    """30. VoiceNotification is strictly tenant-scoped."""
    m_alpha = setup_security_merchants["m_alpha"]
    m_beta = setup_security_merchants["m_beta"]

    dev_b = Device(merchant_id=m_beta.id, device_type=DeviceType.SOUNDBOX.value, device_name="SB", status=DeviceStatus.ACTIVE.value)
    pay_b = Payment(merchant_id=m_beta.id, amount_minor=1000, currency="INR", provider="RAZORPAY", provider_payment_id="pay_x", status=PaymentStatus.CAPTURED.value)
    pg_db.add_all([dev_b, pay_b])
    pg_db.flush()

    notif_b = VoiceNotification(merchant_id=m_beta.id, device_id=dev_b.id, payment_id=pay_b.id, message="Hi", status=VoiceNotificationStatus.PENDING.value)
    pg_db.add(notif_b)
    pg_db.commit()

    assert tenant_service.get_voice_notification_for_merchant(pg_db, notif_b.id, m_alpha.id) is None


def test_staff_cannot_access_owner_only_operation(pg_client, setup_security_merchants):
    """31. STAFF cannot access OWNER-only operation."""
    user_staff = setup_security_merchants["user_staff"]
    m_alpha = setup_security_merchants["m_alpha"]

    res = pg_client.get(
        "/api/v1/merchants/owner-only",
        headers={**auth_header(user_staff), "X-Merchant-ID": str(m_alpha.id)},
    )
    assert res.status_code == 403


def test_admin_cannot_access_owner_only_operation(pg_client, setup_security_merchants):
    """32. ADMIN cannot access OWNER-only operation."""
    user_admin = setup_security_merchants["user_admin"]
    m_alpha = setup_security_merchants["m_alpha"]

    res = pg_client.get(
        "/api/v1/merchants/owner-only",
        headers={**auth_header(user_admin), "X-Merchant-ID": str(m_alpha.id)},
    )
    assert res.status_code == 403


def test_client_supplied_role_cannot_escalate_privileges(pg_client, setup_security_merchants):
    """33. Request cannot escalate role by supplying custom headers/params."""
    user_staff = setup_security_merchants["user_staff"]
    m_alpha = setup_security_merchants["m_alpha"]

    res = pg_client.get(
        "/api/v1/merchants/owner-only",
        headers={
            **auth_header(user_staff),
            "X-Merchant-ID": str(m_alpha.id),
            "X-Role": "OWNER",
        },
    )
    assert res.status_code == 403


def test_multi_merchant_context_cannot_be_confused(pg_client, pg_db, setup_security_merchants):
    """34. Multi-merchant user must supply explicit context and cannot leak state."""
    user_staff = setup_security_merchants["user_staff"]
    m_alpha = setup_security_merchants["m_alpha"]
    m_beta = setup_security_merchants["m_beta"]

    # Add staff to beta as well
    pg_db.add(MerchantUser(merchant_id=m_beta.id, user_id=user_staff.id, role="STAFF"))
    pg_db.commit()

    # Ambiguous request without header is rejected
    res_ambiguous = pg_client.get("/api/v1/merchants/context", headers=auth_header(user_staff))
    assert res_ambiguous.status_code == 400

    # Explicit requests resolve correctly
    res_alpha = pg_client.get(
        "/api/v1/merchants/context",
        headers={**auth_header(user_staff), "X-Merchant-ID": str(m_alpha.id)},
    )
    assert res_alpha.status_code == 200
    assert res_alpha.json()["id"] == str(m_alpha.id)


# =====================================================================
# 5. Security Configuration & Sanitization Tests (35-39)
# =====================================================================

def test_jwt_secret_not_hardcoded():
    """35. JWT secret is loaded from settings, not hardcoded."""
    assert hasattr(settings, "JWT_SECRET")
    assert isinstance(settings.JWT_SECRET, str)
    assert len(settings.JWT_SECRET) >= 32


def test_production_configuration_rejects_insecure_secret():
    """36. Production environment rejects weak or default secrets."""
    with pytest.raises(ValueError, match="Production configuration error"):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET="voiceledger_jwt_signing_secret_dev_environment_key_2026_min_32",
        )

    with pytest.raises(ValueError, match="Production configuration error"):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET="too_short",
        )


def test_secrets_absent_from_api_responses(pg_client, setup_security_merchants):
    """37. Secrets are completely absent from API responses."""
    user = setup_security_merchants["user_owner"]
    res = pg_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "SecurePassword123!"},
    )
    assert res.status_code == 200
    text = res.text
    assert settings.JWT_SECRET not in text
    assert "postgres" not in text.lower()


def test_sensitive_authentication_data_absent_from_logs(pg_client, caplog):
    """38. Sensitive credentials do not leak into logger output."""
    raw_pass = "TestUnloggedPassword999!"
    pg_client.post(
        "/api/v1/auth/register",
        json={"email": f"unlogged_{uuid.uuid4().hex[:6]}@example.com", "password": raw_pass},
    )
    assert raw_pass not in caplog.text


def test_sensitive_authentication_data_sanitized_for_audit():
    """39. sanitize_sensitive_data recursively redacts passwords, tokens, secrets, and hashes."""
    data = {
        "event": "user_action",
        "password": "SuperSecretPassword!",
        "access_token": "eyJhbGciOi...",
        "refresh_token": "opaque_refresh_123",
        "token_hash": "sha256_hash_value",
        "nested": {
            "jwt_secret": "signing_key",
            "webhook_secret": "wh_sec",
            "safe_field": "safe_value",
        },
        "list_field": [
            {"raw_password": "nested_password", "user_id": "12345"},
        ],
    }
    sanitized = sanitize_sensitive_data(data)
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["access_token"] == "[REDACTED]"
    assert sanitized["refresh_token"] == "[REDACTED]"
    assert sanitized["token_hash"] == "[REDACTED]"
    assert sanitized["nested"]["jwt_secret"] == "[REDACTED]"
    assert sanitized["nested"]["webhook_secret"] == "[REDACTED]"
    assert sanitized["nested"]["safe_field"] == "safe_value"
    assert sanitized["list_field"][0]["raw_password"] == "[REDACTED]"
    assert sanitized["list_field"][0]["user_id"] == "12345"


# =====================================================================
# Additional Baseline Hardening: Security Headers & Mutation Scoping
# =====================================================================

def test_security_headers_present_on_responses(pg_client):
    """Security headers are injected on API responses."""
    res = pg_client.get("/health")
    # Headers must be present on every response regardless of 200/503 status
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert res.headers.get("X-XSS-Protection") == "1; mode=block"
    assert res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_tenant_mutation_isolation(pg_db, setup_security_merchants):
    """Mutations across tenants (update/delete) are strictly prevented by tenant_service."""
    m_alpha = setup_security_merchants["m_alpha"]
    m_beta = setup_security_merchants["m_beta"]

    d_beta = Device(
        merchant_id=m_beta.id,
        device_type=DeviceType.SOUNDBOX.value,
        device_name="Beta Device",
        status=DeviceStatus.ACTIVE.value,
    )
    pg_db.add(d_beta)
    pg_db.commit()

    # Alpha attempts to update Beta's device -> returns None (no mutation)
    updated = tenant_service.update_device_for_merchant(
        db=pg_db,
        device_id=d_beta.id,
        merchant_id=m_alpha.id,
        device_name="Hacked Name",
    )
    assert updated is None

    # Verify device remains unchanged
    pg_db.refresh(d_beta)
    assert d_beta.device_name == "Beta Device"

    # Alpha attempts to delete Beta's device -> returns False
    deleted = tenant_service.delete_device_for_merchant(
        db=pg_db,
        device_id=d_beta.id,
        merchant_id=m_alpha.id,
    )
    assert deleted is False
    assert pg_db.query(Device).filter(Device.id == d_beta.id).first() is not None
