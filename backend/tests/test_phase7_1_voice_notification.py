"""
Phase 7.1 — Voice Notification Engine & TTS Provider Boundary Test Suite.

Verifies:
1. Captured Payment: payment.captured event generates a localized voice notification.
2. Refunded Payment: payment.refunded generates the correct refund phrase.
3. Partially Refunded Payment: payment.partially_refunded formats partial refund message.
4. Non-Announced Events: payment.failed and payment.created do NOT generate voice notifications.
5. Idempotency: Duplicate delivery of the same payment event does not create duplicate notifications.
6. English Phrase Formatting: Formats 5000 minor units to "Fifty rupees received", 150000 to
   "One thousand five hundred rupees received", 2500000 to "Twenty five thousand rupees received".
7. Paise Handling: Formats rupees and paise, singular "rupee" / "paisa", and handles negative rejection.
8. Hindi Support: Formats Hindi phrase (e.g. "पचास रुपये प्राप्त हुए").
9. Provider Abstraction: Uses generic TTSProvider interface; zero Razorpay coupling.
10. Audio Artifact Generation: Successful synthesis produces audio artifact in AudioResult format.
11. Failure Isolation: TTS synthesis failure marks VoiceNotification FAILED without altering Payment state.
12. Security Review: Generated voice notification messages and metadata contain no secrets/credentials.
"""
from datetime import datetime, timezone
import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.config import settings
from backend.app.models.merchant import Merchant
from backend.app.models.device import Device, DeviceStatus
from backend.app.models.payment import Payment, PaymentStatus
from backend.app.models.voice_notification import VoiceNotification, VoiceNotificationStatus
from backend.app.providers.tts.base import TTSProvider, AudioResult
from backend.app.providers.tts.mock import MockTTSProvider
from backend.app.services.voice_formatter import format_amount_in_words, format_voice_phrase
from backend.app.services.voice_notification_service import voice_notification_service

# Authoritative PostgreSQL connection for test fixture setup
pg_engine = create_engine(settings.DATABASE_URL)
PGTestSession = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)


@pytest.fixture
def voice_tenancy():
    """Create committed test merchant, device, and payment in PostgreSQL."""
    db = PGTestSession()
    cleanup_merchant_ids = []

    try:
        # Merchant
        merchant = Merchant(
            id=uuid.uuid4(),
            name="Voice Test Kirana",
            business_type="Retail",
            status="ACTIVE",
            currency="INR",
        )
        db.add(merchant)
        cleanup_merchant_ids.append(merchant.id)
        db.flush()

        # Soundbox Device
        device = Device(
            id=uuid.uuid4(),
            merchant_id=merchant.id,
            device_name="Counter 1 Soundbox",
            status=DeviceStatus.ACTIVE.value,
        )
        db.add(device)
        db.flush()

        # Payment
        payment = Payment(
            id=uuid.uuid4(),
            merchant_id=merchant.id,
            provider="RAZORPAY",
            provider_payment_id=f"pay_{uuid.uuid4().hex[:12]}",
            amount_minor=5000,  # ₹50.00
            currency="INR",
            status=PaymentStatus.CAPTURED.value,
        )
        db.add(payment)
        db.commit()

        yield {
            "merchant": merchant,
            "device": device,
            "payment": payment,
        }

    finally:
        db.query(VoiceNotification).delete()
        db.query(Payment).delete()
        db.query(Device).delete()
        db.query(Merchant).filter(Merchant.id.in_(cleanup_merchant_ids)).delete(synchronize_session=False)
        db.commit()
        db.close()


# =====================================================================
# 1. Deterministic Voice Phrase & Amount Formatting Tests
# =====================================================================

def test_english_phrase_formatting_examples():
    """Verify prompt examples: ₹50, ₹1,500, ₹25,000 generate expected English phrases."""
    # ₹50 (5,000 minor)
    phrase_50 = format_voice_phrase("payment.captured", 5000)
    assert phrase_50 == "Fifty rupees received"

    # ₹1,500 (150,000 minor)
    phrase_1500 = format_voice_phrase("payment.captured", 150000)
    assert phrase_1500 == "One thousand five hundred rupees received"

    # ₹25,000 (2,500,000 minor)
    phrase_25000 = format_voice_phrase("payment.captured", 2500000)
    assert phrase_25000 == "Twenty five thousand rupees received"


def test_amount_minor_paise_and_edge_cases():
    """Verify amount formatting handles paise, singular rupee, zero, and rejects negative amounts."""
    # Singular rupee
    assert format_amount_in_words(100) == "One rupee"

    # Rupees and paise (₹50.50 = 5050 minor)
    assert format_amount_in_words(5050) == "Fifty rupees and fifty paise"

    # Only paise (₹0.75 = 75 minor)
    assert format_amount_in_words(75) == "Seventy five paise"

    # Singular paisa (₹0.01 = 1 minor)
    assert format_amount_in_words(1) == "One paisa"

    # Zero
    assert format_amount_in_words(0) == "Zero rupees"

    # Negative amount rejection
    with pytest.raises(ValueError, match="Amount cannot be negative"):
        format_amount_in_words(-500)


def test_refund_and_partial_refund_phrasing():
    """Verify phrases for refund and partial refund lifecycle transitions."""
    refund_phrase = format_voice_phrase("payment.refunded", 5000)
    assert refund_phrase == "Fifty rupees refunded"

    partial_phrase = format_voice_phrase("payment.partially_refunded", 2000)
    assert partial_phrase == "Twenty rupees partially refunded"


def test_hindi_language_support():
    """Verify Hindi phrase generation for Soundbox announcements."""
    hi_phrase = format_voice_phrase("payment.captured", 5000, language="hi-IN")
    assert "रुपये प्राप्त हुए" in hi_phrase
    assert "पचास" in hi_phrase


def test_unsupported_events_do_not_produce_voice_phrases():
    """Events like payment.created or payment.failed must not generate voice phrases."""
    assert format_voice_phrase("payment.created", 5000) is None
    assert format_voice_phrase("payment.failed", 5000) is None
    assert format_voice_phrase("payment.authorized", 5000) == "Fifty rupees received"


# =====================================================================
# 2. Voice Notification Service & Lifecycle Tests
# =====================================================================

@pytest.mark.asyncio
async def test_captured_payment_creates_voice_notification(voice_tenancy):
    """Captured payment event generates and persists a valid VoiceNotification."""
    db = PGTestSession()
    try:
        merchant = voice_tenancy["merchant"]
        payment = voice_tenancy["payment"]
        device = voice_tenancy["device"]

        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "payment.captured",
            "merchant_id": str(merchant.id),
            "payment_id": str(payment.id),
            "amount_minor": payment.amount_minor,
            "currency": payment.currency,
        }

        notification = await voice_notification_service.process_payment_event_for_voice(
            db=db,
            event_payload=event,
        )

        assert notification is not None
        assert notification.merchant_id == merchant.id
        assert notification.payment_id == payment.id
        assert notification.device_id == device.id
        assert notification.message == "Fifty rupees received"
        assert notification.status == VoiceNotificationStatus.QUEUED.value
        assert notification.delivered_at is not None

        # Verify synthesized audio artifact exists
        audio = voice_notification_service.get_audio_artifact(notification.id)
        assert audio is not None
        assert isinstance(audio.audio_bytes, bytes)
        assert len(audio.audio_bytes) > 0
        assert audio.content_type == "audio/wav"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_failed_payment_does_not_create_notification(voice_tenancy):
    """Failed payment events are safely filtered out with zero database records created."""
    db = PGTestSession()
    try:
        merchant = voice_tenancy["merchant"]
        payment = voice_tenancy["payment"]

        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "payment.failed",
            "merchant_id": str(merchant.id),
            "payment_id": str(payment.id),
            "amount_minor": payment.amount_minor,
        }

        notification = await voice_notification_service.process_payment_event_for_voice(
            db=db,
            event_payload=event,
        )
        assert notification is None
        assert db.query(VoiceNotification).count() == 0
    finally:
        db.close()


@pytest.mark.asyncio
async def test_duplicate_event_idempotency_returns_existing_notification(voice_tenancy):
    """Processing duplicate events for the same payment/device returns existing record."""
    db = PGTestSession()
    try:
        merchant = voice_tenancy["merchant"]
        payment = voice_tenancy["payment"]

        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "payment.captured",
            "merchant_id": str(merchant.id),
            "payment_id": str(payment.id),
            "amount_minor": 5000,
            "currency": "INR",
        }

        # First call
        notif1 = await voice_notification_service.process_payment_event_for_voice(db, event)
        assert notif1 is not None

        # Duplicate call
        notif2 = await voice_notification_service.process_payment_event_for_voice(db, event)
        assert notif2 is not None
        assert notif1.id == notif2.id

        # Exactly 1 row in database
        assert db.query(VoiceNotification).count() == 1
    finally:
        db.close()


# =====================================================================
# 3. Failure Isolation & Architectural Boundaries
# =====================================================================

@pytest.mark.asyncio
async def test_tts_failure_marks_notification_failed_without_payment_mutation(voice_tenancy):
    """TTS provider failure marks VoiceNotification FAILED while Payment remains CAPTURED."""
    db = PGTestSession()
    try:
        merchant = voice_tenancy["merchant"]
        payment = voice_tenancy["payment"]

        # Use failing TTS provider
        failing_provider = MockTTSProvider(simulate_failure=True)

        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "payment.captured",
            "merchant_id": str(merchant.id),
            "payment_id": str(payment.id),
            "amount_minor": 5000,
            "currency": "INR",
        }

        notification = await voice_notification_service.process_payment_event_for_voice(
            db=db,
            event_payload=event,
            tts_provider=failing_provider,
        )

        assert notification is not None
        assert notification.status == VoiceNotificationStatus.FAILED.value
        assert "Simulated TTS synthesis provider failure" in notification.error_message

        # Crucial Architectural Rule: Payment status is untouched
        persisted_payment = db.query(Payment).filter(Payment.id == payment.id).first()
        assert persisted_payment is not None
        assert persisted_payment.status == PaymentStatus.CAPTURED.value
    finally:
        db.close()


def test_voice_data_contains_zero_secrets_or_credentials(voice_tenancy):
    """Notification message contains only spoken amount and action; no keys, tokens, or hashes."""
    phrase = format_voice_phrase("payment.captured", 500000)
    assert "devsec" not in phrase
    assert "devsess" not in phrase
    assert "Bearer" not in phrase
    assert "secret" not in phrase
    assert "key" not in phrase
    assert "hash" not in phrase
    assert phrase == "Five thousand rupees received"


def test_voice_subsystem_has_zero_razorpay_coupling():
    """Verify voice formatter, service, and providers do NOT import Razorpay SDK."""
    import inspect
    import backend.app.services.voice_formatter as vf_mod
    import backend.app.services.voice_notification_service as vns_mod
    import backend.app.providers.tts.base as tb_mod
    import backend.app.providers.tts.mock as tm_mod

    for mod in (vf_mod, vns_mod, tb_mod, tm_mod):
        source = inspect.getsource(mod)
        assert "RazorpayClient" not in source
        assert "RazorpayProvider" not in source
        assert "backend.app.providers.razorpay" not in source
