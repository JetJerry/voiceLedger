import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from alembic.config import Config
from alembic.script import ScriptDirectory

from backend.app.main import app
from backend.app.config import Settings, settings
from backend.app.core.logging import sanitize_log_message


client = TestClient(app)


def test_health_endpoint_healthy():
    """Verify GET /health returns 200 when DB and Redis are both reachable."""
    with patch("backend.app.api.health.check_db_health", return_value=True), \
         patch("backend.app.api.health.check_redis_health", new_callable=AsyncMock, return_value=True):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        assert data["redis"] == "connected"
        assert data["service"] == "VoiceLedger"
        assert "version" in data
        assert "environment" in data


def test_health_endpoint_api_alias():
    """Verify GET /api/health returns 200 and matches /health."""
    with patch("backend.app.api.health.check_db_health", return_value=True), \
         patch("backend.app.api.health.check_redis_health", new_callable=AsyncMock, return_value=True):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


def test_health_endpoint_db_failure():
    """Verify GET /health returns 503 when the database is unreachable."""
    with patch("backend.app.api.health.check_db_health", return_value=False), \
         patch("backend.app.api.health.check_redis_health", new_callable=AsyncMock, return_value=True):
        response = client.get("/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "unreachable"
        assert data["redis"] == "connected"


def test_health_endpoint_redis_failure():
    """Verify GET /health returns 503 when Redis is unreachable."""
    with patch("backend.app.api.health.check_db_health", return_value=True), \
         patch("backend.app.api.health.check_redis_health", new_callable=AsyncMock, return_value=False):
        response = client.get("/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "connected"
        assert data["redis"] == "unreachable"


def test_request_id_middleware():
    """Verify X-Request-ID header is propagated and returned in response."""
    # 1. Custom request ID passed by client
    custom_id = "test-custom-request-id-12345"
    response = client.get("/health", headers={"X-Request-ID": custom_id})
    assert response.headers.get("X-Request-ID") == custom_id

    # 2. Generated request ID when not provided
    response_auto = client.get("/health")
    assert "X-Request-ID" in response_auto.headers
    assert len(response_auto.headers["X-Request-ID"]) > 0


def test_settings_configuration():
    """Verify Settings load and parse PostgreSQL and Redis configuration cleanly."""
    custom_settings = Settings(
        APP_ENV="staging",
        DATABASE_URL="postgresql+psycopg://user:pass@db.internal:5432/ledger_staging",
        REDIS_URL="redis://redis.internal:6379/1",
        CORS_ALLOWED_ORIGINS="http://example.com, https://app.voiceledger.io",
    )
    assert custom_settings.APP_ENV == "staging"
    assert "postgresql+psycopg" in custom_settings.DATABASE_URL
    assert custom_settings.REDIS_URL == "redis://redis.internal:6379/1"
    assert custom_settings.CORS_ALLOWED_ORIGINS == ["http://example.com", "https://app.voiceledger.io"]


def test_logging_sanitization():
    """Verify sensitive patterns are sanitized in logs."""
    test_cases = [
        ('Authorization: Bearer secret_access_token_12345', 'Authorization: [REDACTED]'),
        ('User login password="super_secret_password"', 'User login password=[REDACTED]'),
        ('Webhook received signature="sig_abc123xyz"', 'Webhook received signature=[REDACTED]'),
        ('API key used rzp_test_1234567890abcdef', 'API key used [REDACTED_RZP_KEY]'),
    ]
    for raw_msg, expected in test_cases:
        sanitized = sanitize_log_message(raw_msg)
        assert "[REDACTED" in sanitized
        assert "super_secret_password" not in sanitized
        assert "secret_access_token_12345" not in sanitized


def test_alembic_configuration():
    """Verify Alembic configuration file and script directory load properly."""
    alembic_cfg = Config("backend/alembic.ini")
    script_dir = ScriptDirectory.from_config(alembic_cfg)
    assert script_dir is not None
    # Script directory points to backend/alembic
    assert script_dir.dir.endswith("alembic")
