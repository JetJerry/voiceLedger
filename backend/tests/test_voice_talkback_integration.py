"""
Targeted Integration Tests for VoiceLedger Voice Talkback Assistant.

Verifies:
1. /api/v1/voice/process-text executes with authenticated merchant context.
2. Tenant isolation is maintained in agent state (merchant_id bound strictly to JWT session).
3. Text processing returns valid conversational text, action taken, and optional audio.
4. Unauthenticated requests to /process-text are rejected with 401 Unauthorized.
"""
import uuid
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.config import settings
from backend.app.models.user import User
from backend.app.models.merchant import Merchant
from backend.app.models.merchant_user import MerchantUser
from backend.app.core.security import create_access_token, hash_password

pg_engine = create_engine(settings.DATABASE_URL)
PGTestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)


@pytest.fixture
def db():
    """Transactional session rolled back cleanly after each test."""
    conn = pg_engine.connect()
    trans = conn.begin()
    session = PGTestSessionLocal(bind=conn)
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        conn.close()


@pytest.fixture
def client(db):
    """FastAPI TestClient with overridden get_db to share transaction."""
    from backend.app.db.session import get_db

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def merchant_context(db):
    """Creates a test merchant and user, returning JWT auth headers."""
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"voice_merchant_{suffix}@voiceledger.test",
        hashed_password=hash_password("SecurePass123!"),
        full_name="Voice Test Merchant",
        is_active=True,
    )
    db.add(user)
    db.flush()

    merchant = Merchant(
        name=f"Voice Test Store {suffix}",
        business_type="chai_stall",
        status="ACTIVE",
        currency="INR",
    )
    db.add(merchant)
    db.flush()

    merchant_user = MerchantUser(
        merchant_id=merchant.id,
        user_id=user.id,
        role="OWNER",
    )
    db.add(merchant_user)
    db.flush()

    token = create_access_token(user_id=user.id, email=user.email)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Merchant-Id": str(merchant.id),
    }
    return {
        "user": user,
        "merchant": merchant,
        "headers": headers,
        "token": token,
    }


def test_voice_process_text_unauthenticated(client):
    """Unauthenticated requests to voice processing must return 401."""
    resp = client.post(
        "/api/v1/voice/process-text",
        json={"text": "2 chai 40 rupaye", "language": "hi-IN"},
    )
    assert resp.status_code == 401


def test_voice_process_text_authenticated(client, merchant_context):
    """Authenticated merchant can send natural language and receive a structured reply."""
    headers = merchant_context["headers"]

    from backend.app.schemas.voice import VoiceProcessResponse, VoiceExtractionResult, VoiceItemExtracted

    mock_agent_result = VoiceProcessResponse(
        agent_reply="2 Chai record ho gayi hai. Kul ₹40.",
        action_taken="RECORD_SALE",
        extraction=VoiceExtractionResult(
            intent="record_sale",
            raw_text="2 chai 40 rupaye",
            items=[VoiceItemExtracted(product_name="Chai", quantity=2, unit_price=20.0)],
        ),
        audio_base64="data:audio/mp3;base64,FAKE",
    )

    with patch(
        "backend.app.api.v1.voice.run_voiceledger_agent_workflow",
        return_value=mock_agent_result,
    ) as mock_agent:
        resp = client.post(
            "/api/v1/voice/process-text",
            headers=headers,
            json={"text": "2 chai 40 rupaye", "voice_lang": "hi"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_reply"] == "2 Chai record ho gayi hai. Kul ₹40."
        assert data["action_taken"] == "RECORD_SALE"
        assert data["extraction"]["intent"] == "record_sale"

        # Verify mock was called with the merchant's exact ID injected
        mock_agent.assert_called_once()
        passed_req = mock_agent.call_args[0][1]
        assert passed_req.merchant_id == str(merchant_context["merchant"].id)


def test_voice_speak_endpoint(client, merchant_context):
    """TTS speak endpoint streams MP3 audio bytes."""
    headers = merchant_context["headers"]

    mock_audio = b"\xff\xfb\x90\x00FAKE_MP3_DATA"
    with patch(
        "backend.app.api.v1.voice.tts_service.generate_speech_async",
        new=AsyncMock(return_value=mock_audio),
    ):
        resp = client.get(
            "/api/v1/voice/speak?text=Payment+received&lang=en",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.content == mock_audio
        assert resp.headers["content-type"] == "audio/mp3"
