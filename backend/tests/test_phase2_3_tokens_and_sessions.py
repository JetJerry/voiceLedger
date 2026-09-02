import logging
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.config import settings
from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.models.user_session import UserSession
from backend.app.models.merchant import Merchant
from backend.app.models.payment import Payment, PaymentStatus
from backend.app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_token,
    TokenExpiredError,
    InvalidTokenError,
    TokenReuseError,
)
from backend.app.services.auth_service import auth_service

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
def registered_user(pg_db):
    """Helper to create and return a registered active User."""
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    user = auth_service.register_user(
        db=pg_db,
        email=email,
        password="SecurePassword2026!",
        full_name="Token Test User",
    )
    return user, "SecurePassword2026!"


# =====================================================================
# 1. Access Token Utilities Tests
# =====================================================================

def test_access_token_generation_and_required_claims():
    """1 & 2. Verify access token contains sub, type, jti, iat, exp."""
    user_id = uuid.uuid4()
    email = "claims_test@example.com"
    token = create_access_token(user_id=user_id, email=email)
    assert isinstance(token, str)

    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["type"] == "access"
    assert payload["email"] == email
    assert "jti" in payload
    assert uuid.UUID(payload["jti"])
    assert payload["exp"] > payload["iat"]
    assert payload["exp"] - payload["iat"] == settings.JWT_ACCESS_TTL_MINUTES * 60


def test_access_token_expiration():
    """3 & 6. Verify expired access token raises TokenExpiredError."""
    user_id = uuid.uuid4()
    expired_token = create_access_token(
        user_id=user_id,
        expires_delta=timedelta(seconds=-10),
    )
    with pytest.raises(TokenExpiredError):
        decode_access_token(expired_token)


def test_access_token_invalid_signature():
    """5. Verify token signed with wrong secret fails verification."""
    user_id = uuid.uuid4()
    fake_token = jwt.encode(
        {"sub": str(user_id), "type": "access", "exp": int(datetime.now(timezone.utc).timestamp()) + 3600, "iat": int(datetime.now(timezone.utc).timestamp())},
        "wrong_signing_secret_for_attack_scenario",
        algorithm=settings.JWT_ALGORITHM,
    )
    with pytest.raises(InvalidTokenError):
        decode_access_token(fake_token)


def test_access_token_malformed():
    """7. Verify malformed token strings are safely rejected."""
    for malformed in ["not.a.token", "gibberish", "", None, 12345]:
        with pytest.raises(InvalidTokenError):
            decode_access_token(malformed)


def test_token_type_confusion_refresh_as_access():
    """8. Verify refresh tokens cannot be used as access tokens."""
    # Opaque refresh token
    opaque_refresh = generate_refresh_token()
    with pytest.raises(InvalidTokenError):
        decode_access_token(opaque_refresh)

    # JWT with wrong type claim
    wrong_type_token = jwt.encode(
        {"sub": str(uuid.uuid4()), "type": "refresh", "iat": int(datetime.now(timezone.utc).timestamp()), "exp": int(datetime.now(timezone.utc).timestamp()) + 3600},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    with pytest.raises(InvalidTokenError) as exc:
        decode_access_token(wrong_type_token)
    assert "type" in str(exc.value).lower()


def test_token_type_confusion_access_as_refresh(pg_client, registered_user):
    """9. Verify access token cannot be used at the refresh endpoint."""
    user, password = registered_user
    login_res = pg_client.post("/api/v1/auth/login", json={"email": user.email, "password": password})
    access_token = login_res.json()["access_token"]

    # Attempt refresh using access token
    res = pg_client.post("/api/v1/auth/refresh", json={"refresh_token": access_token})
    assert res.status_code == 401
    assert "invalid" in res.json()["detail"].lower()


def test_signing_configuration_is_not_hardcoded():
    """10. Verify signing configuration is derived from Settings."""
    assert settings.JWT_SECRET != ""
    assert len(settings.JWT_SECRET) >= 32
    assert settings.JWT_ALGORITHM == "HS256"


# =====================================================================
# 2. Login & Token Issuance Tests
# =====================================================================

def test_successful_login_returns_tokens(pg_client, registered_user):
    """11. Verify successful login issues access token, refresh token, and user info."""
    user, password = registered_user
    res = pg_client.post("/api/v1/auth/login", json={"email": user.email, "password": password})
    assert res.status_code == 200
    data = res.json()

    assert data["success"] is True
    assert data["status"] == "authenticated"
    assert data["token_type"] == "bearer"
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["expires_in"] == settings.JWT_ACCESS_TTL_MINUTES * 60
    assert data["user"]["email"] == user.email

    # Verify access token is decodable
    payload = decode_access_token(data["access_token"])
    assert payload["sub"] == str(user.id)


def test_login_incorrect_credentials_generic_error(pg_client, registered_user):
    """12. Verify wrong password returns generic 401 error."""
    user, _ = registered_user
    res = pg_client.post("/api/v1/auth/login", json={"email": user.email, "password": "WrongPassword999!"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid email or password"


def test_login_inactive_user_rejected(pg_client, pg_db, registered_user):
    """13. Verify inactive user cannot authenticate."""
    user, password = registered_user
    user.is_active = False
    pg_db.commit()

    res = pg_client.post("/api/v1/auth/login", json={"email": user.email, "password": password})
    assert res.status_code == 403
    assert "inactive" in res.json()["detail"].lower()


# =====================================================================
# 3. Refresh Token & Rotation Tests
# =====================================================================

def test_refresh_token_rotation(pg_client, registered_user):
    """14, 15 & 16. Verify refresh token rotation: issues new tokens, invalidates old token."""
    user, password = registered_user
    login_res = pg_client.post("/api/v1/auth/login", json={"email": user.email, "password": password})
    old_access = login_res.json()["access_token"]
    old_refresh = login_res.json()["refresh_token"]

    # Rotate refresh token
    refresh_res = pg_client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert refresh_res.status_code == 200
    data = refresh_res.json()

    new_access = data["access_token"]
    new_refresh = data["refresh_token"]

    assert new_access != old_access
    assert new_refresh != old_refresh
    assert data["token_type"] == "bearer"

    # Old refresh token is now unusable
    old_res = pg_client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert old_res.status_code == 401


def test_expired_refresh_token_rejected(pg_client, pg_db, registered_user):
    """17. Verify expired refresh token is rejected."""
    user, password = registered_user
    login_res = pg_client.post("/api/v1/auth/login", json={"email": user.email, "password": password})
    raw_refresh = login_res.json()["refresh_token"]

    # Expire session in PostgreSQL
    token_hash = hash_token(raw_refresh)
    session = pg_db.query(UserSession).filter(UserSession.token_hash == token_hash).first()
    session.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    pg_db.commit()

    res = pg_client.post("/api/v1/auth/refresh", json={"refresh_token": raw_refresh})
    assert res.status_code == 401
    assert "expired" in res.json()["detail"].lower()


def test_revoked_refresh_token_rejected(pg_client, pg_db, registered_user):
    """18. Verify manually revoked refresh token is rejected."""
    user, password = registered_user
    login_res = pg_client.post("/api/v1/auth/login", json={"email": user.email, "password": password})
    raw_refresh = login_res.json()["refresh_token"]

    # Revoke session
    token_hash = hash_token(raw_refresh)
    session = pg_db.query(UserSession).filter(UserSession.token_hash == token_hash).first()
    session.is_revoked = True
    session.revoked_at = datetime.now(timezone.utc)
    pg_db.commit()

    res = pg_client.post("/api/v1/auth/refresh", json={"refresh_token": raw_refresh})
    assert res.status_code == 401


def test_invalid_refresh_token_rejected(pg_client):
    """19. Verify completely unknown refresh token is rejected."""
    res = pg_client.post("/api/v1/auth/refresh", json={"refresh_token": "unknown_refresh_token_string_123"})
    assert res.status_code == 401


def test_refresh_token_stored_only_as_hash(pg_client, pg_db, registered_user):
    """20. Verify plaintext refresh token is never saved in database."""
    user, password = registered_user
    login_res = pg_client.post("/api/v1/auth/login", json={"email": user.email, "password": password})
    raw_refresh = login_res.json()["refresh_token"]

    # Query DB
    expected_hash = hash_token(raw_refresh)
    session = pg_db.query(UserSession).filter(UserSession.token_hash == expected_hash).first()
    assert session is not None
    assert session.token_hash == expected_hash
    assert raw_refresh != session.token_hash


def test_refresh_tokens_never_logged(pg_client, registered_user, caplog):
    """21. Verify refresh token is not written to application logs."""
    user, password = registered_user
    with caplog.at_level(logging.DEBUG):
        login_res = pg_client.post("/api/v1/auth/login", json={"email": user.email, "password": password})
        raw_refresh = login_res.json()["refresh_token"]
        pg_client.post("/api/v1/auth/refresh", json={"refresh_token": raw_refresh})

    for record in caplog.records:
        assert raw_refresh not in record.getMessage()


# =====================================================================
# 4. Token Reuse Detection Tests
# =====================================================================

def test_refresh_token_reuse_detection(pg_client, registered_user):
    """22, 23, 24 & 25. Verify reuse detection revokes the entire token family."""
    user, password = registered_user
    # 1. User logs in -> gets rt1
    login_res = pg_client.post("/api/v1/auth/login", json={"email": user.email, "password": password})
    rt1 = login_res.json()["refresh_token"]

    # 2. Legitimate rotation: rt1 -> rt2
    rot1_res = pg_client.post("/api/v1/auth/refresh", json={"refresh_token": rt1})
    assert rot1_res.status_code == 200
    rt2 = rot1_res.json()["refresh_token"]

    # 3. Legitimate rotation: rt2 -> rt3
    rot2_res = pg_client.post("/api/v1/auth/refresh", json={"refresh_token": rt2})
    assert rot2_res.status_code == 200
    rt3 = rot2_res.json()["refresh_token"]

    # 4. Attacker attempts to reuse rt1 (which was already rotated!)
    reuse_res = pg_client.post("/api/v1/auth/refresh", json={"refresh_token": rt1})
    assert reuse_res.status_code == 401
    assert "revoked" in reuse_res.json()["detail"].lower() or "invalid" in reuse_res.json()["detail"].lower()

    # 5. Subsequent attempts by legitimate user using rt3 MUST now fail because family was revoked!
    subsequent_res = pg_client.post("/api/v1/auth/refresh", json={"refresh_token": rt3})
    assert subsequent_res.status_code == 401


# =====================================================================
# 5. Logout Tests
# =====================================================================

def test_logout_revokes_refresh_session(pg_client, registered_user):
    """26 & 27. Verify logout revokes the refresh session and token cannot be used."""
    user, password = registered_user
    login_res = pg_client.post("/api/v1/auth/login", json={"email": user.email, "password": password})
    refresh_token = login_res.json()["refresh_token"]

    # Logout
    logout_res = pg_client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
    assert logout_res.status_code == 200
    assert logout_res.json()["success"] is True

    # Refresh should fail
    refresh_res = pg_client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_res.status_code == 401


def test_logout_does_not_affect_financial_records(pg_client, pg_db, registered_user):
    """28. Verify logout does not cascade or delete financial/payment records."""
    user, password = registered_user

    # Create a test merchant and payment
    merchant = Merchant(name="Audit Safe Store", business_type="Retail")
    pg_db.add(merchant)
    pg_db.flush()

    payment = Payment(
        merchant_id=merchant.id,
        amount_minor=50000,
        currency="INR",
        provider="RAZORPAY",
        provider_payment_id=f"pay_{uuid.uuid4().hex[:12]}",
        status=PaymentStatus.CAPTURED.value,
    )
    pg_db.add(payment)
    pg_db.commit()

    # Login and Logout
    login_res = pg_client.post("/api/v1/auth/login", json={"email": user.email, "password": password})
    refresh_token = login_res.json()["refresh_token"]
    pg_client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})

    # Assert payment is completely intact
    pg_db.expire_all()
    queried_payment = pg_db.query(Payment).filter(Payment.id == payment.id).first()
    assert queried_payment is not None
    assert queried_payment.amount_minor == 50000


# =====================================================================
# 6. get_current_user Dependency Tests
# =====================================================================

def test_get_current_user_valid_token(pg_client, registered_user):
    """31. Verify get_current_user returns user when valid Bearer token supplied."""
    user, password = registered_user
    login_res = pg_client.post("/api/v1/auth/login", json={"email": user.email, "password": password})
    access_token = login_res.json()["access_token"]

    res = pg_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == str(user.id)
    assert data["email"] == user.email


def test_get_current_user_missing_header(pg_client):
    """29. Verify missing Authorization header returns 401."""
    res = pg_client.get("/api/v1/auth/me")
    assert res.status_code == 401
    assert "not authenticated" in res.json()["detail"].lower()


def test_get_current_user_invalid_bearer_token(pg_client):
    """30. Verify invalid Bearer token returns 401."""
    res = pg_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.signature.token"},
    )
    assert res.status_code == 401
    assert "invalid" in res.json()["detail"].lower()


def test_get_current_user_inactive_user(pg_client, pg_db, registered_user):
    """32. Verify access token for an inactive user returns 403 Forbidden."""
    user, password = registered_user
    login_res = pg_client.post("/api/v1/auth/login", json={"email": user.email, "password": password})
    access_token = login_res.json()["access_token"]

    # Deactivate user
    user.is_active = False
    pg_db.commit()

    res = pg_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert res.status_code == 403
    assert "inactive" in res.json()["detail"].lower()


# =====================================================================
# 7. Security & Non-Leakage Tests
# =====================================================================

def test_jwt_secrets_and_refresh_hashes_never_in_responses(pg_client, registered_user):
    """33 & 34. Verify secrets and token hashes are never exposed in API responses."""
    user, password = registered_user
    login_res = pg_client.post("/api/v1/auth/login", json={"email": user.email, "password": password})
    assert settings.JWT_SECRET not in login_res.text
    assert "token_hash" not in login_res.text

    refresh_res = pg_client.post("/api/v1/auth/refresh", json={"refresh_token": login_res.json()["refresh_token"]})
    assert settings.JWT_SECRET not in refresh_res.text
    assert "token_hash" not in refresh_res.text


def test_database_exceptions_not_exposed_to_clients_refresh(pg_client):
    """36. Verify internal database exceptions are intercepted and sanitized."""
    with patch("backend.app.services.auth_service.auth_service.rotate_refresh_token", side_effect=Exception("Raw PostgreSQL Deadlock")):
        res = pg_client.post("/api/v1/auth/refresh", json={"refresh_token": "some_token"})
        assert res.status_code == 500
        assert "PostgreSQL" not in res.text
        assert "Deadlock" not in res.text
        assert res.json()["detail"] == "An error occurred during token refresh"


def test_expired_access_token_at_me_endpoint(pg_client):
    """Verify expired access token at protected /me endpoint returns 401 with detail."""
    user_id = uuid.uuid4()
    expired_token = create_access_token(user_id=user_id, expires_delta=timedelta(seconds=-1))
    res = pg_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert res.status_code == 401
    assert "token has expired" in res.json()["detail"].lower()


def test_logout_with_none_or_empty_token_is_safe(pg_client):
    """Verify logout with null/empty refresh token completes idempotently without error."""
    res = pg_client.post("/api/v1/auth/logout", json={})
    assert res.status_code == 200
    assert res.json()["success"] is True
