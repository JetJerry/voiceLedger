import logging
import uuid
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.config import settings
from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.schemas.auth import UserResponse
from backend.app.services.auth_service import (
    auth_service,
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    UserInactiveError,
)

# Canonical PostgreSQL Engine for Phase 2 tests
pg_engine = create_engine(settings.DATABASE_URL)
PGTestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)


@pytest.fixture
def pg_db():
    """
    Transactional PostgreSQL session for canonical VoiceLedger tests.
    Every test runs in a transaction that is rolled back upon completion.
    """
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
    """
    FastAPI TestClient with get_db overridden to use the transactional PostgreSQL session.
    """
    def override_get_db():
        yield pg_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


# =====================================================================
# Registration Tests
# =====================================================================

def test_successful_registration(pg_client, pg_db):
    """1. Verify successful registration returns 201 and safe user profile."""
    email = f"merchant_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "email": email,
        "password": "SecurePassword2026!",
        "full_name": "Ramesh Kumar",
    }
    response = pg_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["message"] == "User registered successfully"
    assert "user" in data
    assert data["user"]["email"] == email.lower()
    assert data["user"]["full_name"] == "Ramesh Kumar"
    assert data["user"]["is_active"] is True
    assert data["user"]["is_superuser"] is False
    assert "id" in data["user"]


def test_password_stored_only_as_argon2id_hash(pg_client, pg_db):
    """2. Verify that password is encrypted with Argon2id and plaintext is never stored."""
    email = f"hash_test_{uuid.uuid4().hex[:8]}@example.com"
    raw_password = "PlaintextPasswordToVerify#"
    payload = {
        "email": email,
        "password": raw_password,
    }
    response = pg_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201

    # Query directly from PostgreSQL
    user = pg_db.query(User).filter(User.email == email).first()
    assert user is not None
    assert user.hashed_password.startswith("$argon2id$")
    assert raw_password != user.hashed_password
    assert raw_password not in user.hashed_password
    assert user.verify_password(raw_password) is True


def test_password_and_hash_never_returned_in_registration_response(pg_client):
    """3 & 4. Verify neither plaintext password nor password hash appears in response."""
    email = f"leak_test_{uuid.uuid4().hex[:8]}@example.com"
    raw_password = "PasswordToCheckForLeakage1!"
    payload = {
        "email": email,
        "password": raw_password,
    }
    response = pg_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    res_text = response.text

    assert raw_password not in res_text
    assert "$argon2id$" not in res_text
    assert "hashed_password" not in response.json()["user"]


def test_duplicate_email_is_rejected(pg_client):
    """5. Verify duplicate email registration fails with 409 Conflict."""
    email = f"duplicate_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "email": email,
        "password": "FirstRegistrationPass123!",
    }
    # First registration
    res1 = pg_client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    # Second registration with same email
    res2 = pg_client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 409
    assert "already registered" in res2.json()["detail"].lower()


def test_email_normalization_works_consistently(pg_client, pg_db):
    """6. Verify email normalization handles mixed casing and surrounding whitespace."""
    raw_email = f"   User.Case_{uuid.uuid4().hex[:6]}@EXAMPLE.COM   "
    clean_email = raw_email.strip().lower()
    payload = {
        "email": raw_email,
        "password": "PasswordWithNormalizedEmail123!",
    }
    res = pg_client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201
    assert res.json()["user"]["email"] == clean_email

    # Verify duplicate check detects with different casing/whitespace
    dup_payload = {
        "email": clean_email.upper(),
        "password": "AnotherPassword123!",
    }
    res_dup = pg_client.post("/api/v1/auth/register", json=dup_payload)
    assert res_dup.status_code == 409

    # Verify login succeeds using uppercase variant
    login_payload = {
        "email": clean_email.upper(),
        "password": "PasswordWithNormalizedEmail123!",
    }
    login_res = pg_client.post("/api/v1/auth/login", json=login_payload)
    assert login_res.status_code == 200
    assert login_res.json()["user"]["email"] == clean_email


def test_invalid_password_input_rejected(pg_client):
    """7. Verify password validation bounds (too short, too long)."""
    email = f"pw_val_{uuid.uuid4().hex[:8]}@example.com"

    # Too short (< 8 chars)
    res_short = pg_client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "short",
    })
    assert res_short.status_code in [400, 422]

    # Too long (> 128 chars)
    res_long = pg_client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "P" * 129,
    })
    assert res_long.status_code in [400, 422]


def test_invalid_email_input_rejected(pg_client):
    """8. Verify malformed email addresses are rejected."""
    for bad_email in ["not-an-email", "@missing-local.com", "missing-domain@", "spaces in@email.com"]:
        res = pg_client.post("/api/v1/auth/register", json={
            "email": bad_email,
            "password": "ValidPassword123!",
        })
        assert res.status_code in [400, 422]


def test_database_transaction_rolls_back_on_failure(pg_db):
    """9. Verify atomic transaction rollback if database error occurs."""
    email = f"rollback_{uuid.uuid4().hex[:8]}@example.com"

    with patch.object(pg_db, "commit", side_effect=RuntimeError("Simulated DB Disk Full")):
        with pytest.raises(RuntimeError):
            auth_service.register_user(
                db=pg_db,
                email=email,
                password="ValidPassword123!",
            )

    # Confirm user was not persisted
    user = pg_db.query(User).filter(User.email == email).first()
    assert user is None


# =====================================================================
# Login & Credential Verification Tests
# =====================================================================

def test_login_with_correct_credentials_accepted(pg_client):
    """10. Verify login accepts correct email and password."""
    email = f"login_success_{uuid.uuid4().hex[:8]}@example.com"
    password = "CorrectLoginPassword2026!"

    # Register user first
    reg_res = pg_client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert reg_res.status_code == 201

    # Login
    login_res = pg_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_res.status_code == 200
    data = login_res.json()
    assert data["success"] is True
    assert data["status"] == "authenticated"
    assert data["message"] == "Credentials verified successfully"
    assert data["user"]["email"] == email.lower()


def test_login_with_incorrect_password_rejected(pg_client):
    """11. Verify login with wrong password returns 401 with generic error message."""
    email = f"wrong_pw_{uuid.uuid4().hex[:8]}@example.com"
    password = "CorrectLoginPassword2026!"

    pg_client.post("/api/v1/auth/register", json={"email": email, "password": password})

    login_res = pg_client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "IncorrectPassword999!",
    })
    assert login_res.status_code == 401
    assert login_res.json()["detail"] == "Invalid email or password"


def test_login_with_unknown_email_rejected(pg_client):
    """12. Verify login with non-existent email returns 401 with generic error message."""
    login_res = pg_client.post("/api/v1/auth/login", json={
        "email": "completely_unknown_user@example.com",
        "password": "SomePassword123!",
    })
    assert login_res.status_code == 401
    assert login_res.json()["detail"] == "Invalid email or password"


def test_unknown_email_and_incorrect_password_produce_identical_error(pg_client):
    """13. Verify that account enumeration is prevented via identical error responses."""
    email = f"enum_test_{uuid.uuid4().hex[:8]}@example.com"
    password = "RealPassword2026!"

    pg_client.post("/api/v1/auth/register", json={"email": email, "password": password})

    # Non-existent user
    res_unknown = pg_client.post("/api/v1/auth/login", json={
        "email": "non_existent_random_user@example.com",
        "password": "WrongPassword123!",
    })

    # Existing user with wrong password
    res_wrong_pw = pg_client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "WrongPassword123!",
    })

    assert res_unknown.status_code == 401
    assert res_wrong_pw.status_code == 401
    assert res_unknown.json() == res_wrong_pw.json()
    assert res_unknown.json()["detail"] == "Invalid email or password"


def test_login_never_exposes_password_or_hash(pg_client):
    """14. Verify login response never exposes password or hash."""
    email = f"safe_login_{uuid.uuid4().hex[:8]}@example.com"
    password = "SafePassword2026!"

    pg_client.post("/api/v1/auth/register", json={"email": email, "password": password})

    login_res = pg_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_res.status_code == 200

    res_text = login_res.text
    assert password not in res_text
    assert "$argon2id$" not in res_text
    assert "hashed_password" not in login_res.json()["user"]


def test_inactive_user_login_rejected(pg_client, pg_db):
    """15. Verify that inactive users cannot log in even with correct credentials."""
    email = f"inactive_{uuid.uuid4().hex[:8]}@example.com"
    password = "CorrectPassword2026!"

    # Create inactive user directly
    user = User(
        email=email,
        is_active=False,
    )
    user.set_password(password)
    pg_db.add(user)
    pg_db.commit()

    login_res = pg_client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password,
    })
    assert login_res.status_code == 403
    assert "inactive" in login_res.json()["detail"].lower()


# =====================================================================
# Security & Leakage Tests
# =====================================================================

def test_database_exceptions_not_exposed_to_clients(pg_client):
    """16. Verify that raw database exceptions are caught and sanitized."""
    with patch("backend.app.services.auth_service.auth_service.register_user", side_effect=Exception("Internal PostgreSQL syntax error")):
        res = pg_client.post("/api/v1/auth/register", json={
            "email": "test_crash@example.com",
            "password": "ValidPassword123!",
        })
        assert res.status_code == 500
        assert "PostgreSQL" not in res.text
        assert "syntax error" not in res.text
        assert res.json()["detail"] == "An error occurred during registration"


def test_passwords_are_not_logged(pg_client, caplog):
    """17. Verify passwords are never recorded in log files."""
    email = f"nolog_{uuid.uuid4().hex[:8]}@example.com"
    secret_pw = "SuperSecretPasswordDoNotLog123!"

    with caplog.at_level(logging.DEBUG):
        pg_client.post("/api/v1/auth/register", json={"email": email, "password": secret_pw})
        pg_client.post("/api/v1/auth/login", json={"email": email, "password": secret_pw})

    for record in caplog.records:
        assert secret_pw not in record.getMessage()


def test_user_response_serialization_cannot_expose_hashed_password():
    """18. Verify UserResponse model schema inherently excludes hashed_password."""
    user = User(
        email="schema_test@example.com",
        full_name="Schema Tester",
    )
    user.set_password("SomePassword123!")

    # Serialize via Pydantic UserResponse
    user_schema = UserResponse.model_validate(user)
    dumped = user_schema.model_dump()

    assert "hashed_password" not in dumped
    assert "password" not in dumped
    assert dumped["email"] == "schema_test@example.com"
