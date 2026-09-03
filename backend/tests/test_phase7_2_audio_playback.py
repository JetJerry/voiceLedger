"""
Phase 7.2 — Voice Audio Streaming & Soundbox Playback Protocol Test Suite.

Verifies:
1. Authenticated Device Delivery: Authenticated Soundbox receives voice notification over /ws/device.
2. Audio Payload Integrity: Valid audio_content_type (audio/wav) and valid base64 WAV RIFF bytes.
3. Device Isolation: Targeted notification to Device 1 is never delivered to Device 2.
4. Cross-Merchant Rejection: Merchant B device cannot receive Merchant A notifications.
5. Audio Validation & Guardrails: Rejects disallowed MIME types and oversized (>2MB) audio.
6. Valid PLAYED ACK: Soundbox playback ACK transitions notification status to DELIVERED with delivered_at.
7. FAILED ACK: Soundbox playback failure transitions notification status to FAILED with error_message.
8. Duplicate ACK Idempotency: Multiple PLAYED ACKs return DELIVERED idempotently without errors.
9. Unauthorized ACK Rejection: Device 2 cannot ACK Device 1's notification; state remains protected.
10. Disconnect Preservation: Device disconnecting before ACK leaves notification in QUEUED status.
11. Financial Safety: Playback failure never mutates Payment status or ledger records (Payment remains CAPTURED).
"""
import base64
from datetime import datetime, timezone
import json
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.config import settings
from backend.app.models.merchant import Merchant
from backend.app.models.device import Device, DeviceStatus
from backend.app.models.device_session import DeviceSession
from backend.app.models.payment import Payment, PaymentStatus
from backend.app.models.voice_notification import VoiceNotification, VoiceNotificationStatus
from backend.app.providers.tts.base import AudioResult
from backend.app.providers.tts.mock import MockTTSProvider
from backend.app.services.device_service import device_service
from backend.app.services.voice_notification_service import (
    voice_notification_service,
    VoiceNotificationAudioError,
    VoiceNotificationForbiddenError,
)

# Authoritative PostgreSQL connection for test fixture setup
pg_engine = create_engine(settings.DATABASE_URL)
PGTestSession = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def playback_tenancy():
    """Create test merchants, devices, payments, and active device sessions."""
    db = PGTestSession()
    cleanup_merchant_ids = []

    try:
        # Merchant A
        merchant_a = Merchant(
            id=uuid.uuid4(),
            name="Kirana A Grocery",
            business_type="Retail",
            status="ACTIVE",
            currency="INR",
        )
        db.add(merchant_a)
        cleanup_merchant_ids.append(merchant_a.id)

        # Merchant B
        merchant_b = Merchant(
            id=uuid.uuid4(),
            name="Kirana B Sweets",
            business_type="Retail",
            status="ACTIVE",
            currency="INR",
        )
        db.add(merchant_b)
        cleanup_merchant_ids.append(merchant_b.id)
        db.flush()

        # Device A1 (Merchant A)
        device_a1, secret_a1 = device_service.register_device(
            db=db,
            merchant_id=merchant_a.id,
            device_name="A1 Counter Soundbox",
        )
        # Device A2 (Merchant A)
        device_a2, secret_a2 = device_service.register_device(
            db=db,
            merchant_id=merchant_a.id,
            device_name="A2 Exit Soundbox",
        )
        # Device B1 (Merchant B)
        device_b1, secret_b1 = device_service.register_device(
            db=db,
            merchant_id=merchant_b.id,
            device_name="B1 Counter Soundbox",
        )
        db.flush()

        # Payments for Merchant A
        payment_a = Payment(
            id=uuid.uuid4(),
            merchant_id=merchant_a.id,
            provider="RAZORPAY",
            provider_payment_id=f"pay_{uuid.uuid4().hex[:12]}",
            amount_minor=5000,  # ₹50.00
            currency="INR",
            status=PaymentStatus.CAPTURED.value,
        )
        db.add(payment_a)

        # Authenticate sessions
        sess_a1, token_a1 = device_service.authenticate_device(db=db, device_id=device_a1.id, raw_secret=secret_a1)
        sess_a2, token_a2 = device_service.authenticate_device(db=db, device_id=device_a2.id, raw_secret=secret_a2)
        sess_b1, token_b1 = device_service.authenticate_device(db=db, device_id=device_b1.id, raw_secret=secret_b1)

        db.commit()

        yield {
            "merchant_a": merchant_a,
            "merchant_b": merchant_b,
            "device_a1": device_a1,
            "device_a2": device_a2,
            "device_b1": device_b1,
            "payment_a": payment_a,
            "token_a1": token_a1,
            "token_a2": token_a2,
            "token_b1": token_b1,
        }

    finally:
        db.query(VoiceNotification).delete()
        db.query(Payment).delete()
        db.query(DeviceSession).delete()
        db.query(Device).delete()
        db.query(Merchant).filter(Merchant.id.in_(cleanup_merchant_ids)).delete(synchronize_session=False)
        db.commit()
        db.close()


# =====================================================================
# 1. Real-Time Audio Streaming & Protocol Tests
# =====================================================================

@pytest.mark.asyncio
async def test_authenticated_device_receives_voice_notification(client, playback_tenancy):
    """Authenticated Soundbox receives streamed voice notification payload over /ws/device."""
    token_a1 = playback_tenancy["token_a1"]
    device_a1 = playback_tenancy["device_a1"]
    merchant_a = playback_tenancy["merchant_a"]
    payment_a = playback_tenancy["payment_a"]

    db = PGTestSession()
    try:
        # Synthesize notification and audio
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "payment.captured",
            "merchant_id": str(merchant_a.id),
            "payment_id": str(payment_a.id),
            "amount_minor": 5000,
            "currency": "INR",
        }
        notif = await voice_notification_service.process_payment_event_for_voice(
            db=db,
            event_payload=event,
            target_device_id=device_a1.id,
        )
        assert notif is not None

        # Connect Soundbox
        with client.websocket_connect(f"/ws/device?token={token_a1}") as ws:
            # Dispatch to device
            delivered = await voice_notification_service.dispatch_notification_to_device(notif)
            assert delivered is True

            # Device receives voice notification
            msg = ws.receive_json()
            assert msg["type"] == "voice_notification"
            assert msg["notification_id"] == str(notif.id)
            assert msg["device_id"] == str(device_a1.id)
            assert msg["text"] == "Fifty rupees received"
            assert msg["audio_content_type"] == "audio/wav"
            assert "audio_data" in msg
    finally:
        db.close()


def test_audio_payload_contains_valid_content_and_base64_wav(playback_tenancy):
    """Audio payload contains base64 encoded PCM WAV bytes with valid RIFF header."""
    device_a1 = playback_tenancy["device_a1"]
    merchant_a = playback_tenancy["merchant_a"]
    payment_a = playback_tenancy["payment_a"]

    notif = VoiceNotification(
        id=uuid.uuid4(),
        merchant_id=merchant_a.id,
        device_id=device_a1.id,
        payment_id=payment_a.id,
        message="One hundred rupees received",
        status=VoiceNotificationStatus.QUEUED.value,
    )
    # Valid minimal PCM WAV mock
    dummy_wav = b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    audio = AudioResult(audio_bytes=dummy_wav, content_type="audio/wav", duration_seconds=1.5)

    payload = voice_notification_service.prepare_audio_payload(notif, audio)
    assert payload["audio_content_type"] == "audio/wav"
    decoded = base64.b64decode(payload["audio_data"])
    assert decoded.startswith(b"RIFF")
    assert b"WAVE" in decoded


@pytest.mark.asyncio
async def test_unauthorized_device_cannot_receive_another_devices_notification(client, playback_tenancy):
    """Targeted notification to Device 1 is never delivered to Device 2."""
    token_a1 = playback_tenancy["token_a1"]
    token_a2 = playback_tenancy["token_a2"]
    device_a1 = playback_tenancy["device_a1"]
    device_a2 = playback_tenancy["device_a2"]
    merchant_a = playback_tenancy["merchant_a"]
    payment_a = playback_tenancy["payment_a"]

    db = PGTestSession()
    try:
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "payment.captured",
            "merchant_id": str(merchant_a.id),
            "payment_id": str(payment_a.id),
            "amount_minor": 5000,
            "currency": "INR",
        }
        notif = await voice_notification_service.process_payment_event_for_voice(
            db=db,
            event_payload=event,
            target_device_id=device_a1.id,
        )

        with client.websocket_connect(f"/ws/device?token={token_a1}") as ws_a1:
            with client.websocket_connect(f"/ws/device?token={token_a2}") as ws_a2:
                # Dispatch targeted to device A1
                delivered = await voice_notification_service.dispatch_notification_to_device(notif)
                assert delivered is True

                # Device A1 receives notification
                msg_a1 = ws_a1.receive_json()
                assert msg_a1["device_id"] == str(device_a1.id)

                # Device A2 should NOT receive Device A1's notification
                ws_a2.send_text("ping")
                assert ws_a2.receive_text() == "pong"
    finally:
        db.close()


def test_cross_merchant_notification_rejection(playback_tenancy):
    """Attempting to record an ACK or dispatch across tenant boundary is blocked."""
    db = PGTestSession()
    try:
        device_b1 = playback_tenancy["device_b1"]
        merchant_a = playback_tenancy["merchant_a"]
        payment_a = playback_tenancy["payment_a"]
        device_a1 = playback_tenancy["device_a1"]

        notif_a = VoiceNotification(
            id=uuid.uuid4(),
            merchant_id=merchant_a.id,
            device_id=device_a1.id,
            payment_id=payment_a.id,
            message="Fifty rupees received",
            status=VoiceNotificationStatus.QUEUED.value,
        )
        db.add(notif_a)
        db.commit()

        # Device B1 (Merchant B) tries to ACK notification belonging to Merchant A / Device A1
        with pytest.raises(VoiceNotificationForbiddenError):
            voice_notification_service.record_playback_ack(
                db=db,
                device_id=device_b1.id,
                notification_id=notif_a.id,
                ack_status="PLAYED",
            )
    finally:
        db.close()


def test_invalid_and_oversized_audio_rejected(playback_tenancy):
    """Audio validation rejects disallowed content types and oversized payloads."""
    device_a1 = playback_tenancy["device_a1"]
    merchant_a = playback_tenancy["merchant_a"]
    payment_a = playback_tenancy["payment_a"]

    notif = VoiceNotification(
        id=uuid.uuid4(),
        merchant_id=merchant_a.id,
        device_id=device_a1.id,
        payment_id=payment_a.id,
        message="Fifty rupees received",
        status=VoiceNotificationStatus.QUEUED.value,
    )

    # 1. Disallowed content type
    disallowed_audio = AudioResult(audio_bytes=b"malicious_bytes", content_type="application/x-sh")
    with pytest.raises(VoiceNotificationAudioError, match="Disallowed audio content-type"):
        voice_notification_service.prepare_audio_payload(notif, disallowed_audio)

    # 2. Oversized audio (> 2MB)
    oversized_audio = AudioResult(audio_bytes=b"0" * (2 * 1024 * 1024 + 100), content_type="audio/wav")
    with pytest.raises(VoiceNotificationAudioError, match="exceeds maximum limit"):
        voice_notification_service.prepare_audio_payload(notif, oversized_audio)


# =====================================================================
# 2. Playback ACK Lifecycle & Idempotency Tests
# =====================================================================

def test_valid_played_ack_updates_notification_correctly(client, playback_tenancy):
    """Soundbox sending PLAYED ACK transitions notification status to DELIVERED with timestamp."""
    token_a1 = playback_tenancy["token_a1"]
    device_a1 = playback_tenancy["device_a1"]
    merchant_a = playback_tenancy["merchant_a"]
    payment_a = playback_tenancy["payment_a"]

    db = PGTestSession()
    try:
        notif = VoiceNotification(
            id=uuid.uuid4(),
            merchant_id=merchant_a.id,
            device_id=device_a1.id,
            payment_id=payment_a.id,
            message="Fifty rupees received",
            status=VoiceNotificationStatus.QUEUED.value,
        )
        db.add(notif)
        db.commit()

        with client.websocket_connect(f"/ws/device?token={token_a1}") as ws:
            # Consume replayed notification received on connect
            replayed = ws.receive_json()
            assert replayed["type"] == "voice_notification"

            ws.send_json({
                "type": "playback_ack",
                "notification_id": str(notif.id),
                "status": "PLAYED",
            })
            resp = ws.receive_json()
            assert resp["type"] == "playback_ack_response"
            assert resp["notification_id"] == str(notif.id)
            assert resp["status"] == VoiceNotificationStatus.DELIVERED.value

        # Verify in DB
        db.expire_all()
        persisted = db.query(VoiceNotification).filter(VoiceNotification.id == notif.id).first()
        assert persisted.status == VoiceNotificationStatus.DELIVERED.value
        assert persisted.delivered_at is not None
        assert persisted.error_message is None
    finally:
        db.close()


def test_failed_ack_marks_notification_failed(client, playback_tenancy):
    """Soundbox sending FAILED ACK transitions notification status to FAILED with error detail."""
    token_a1 = playback_tenancy["token_a1"]
    device_a1 = playback_tenancy["device_a1"]
    merchant_a = playback_tenancy["merchant_a"]
    payment_a = playback_tenancy["payment_a"]

    db = PGTestSession()
    try:
        notif = VoiceNotification(
            id=uuid.uuid4(),
            merchant_id=merchant_a.id,
            device_id=device_a1.id,
            payment_id=payment_a.id,
            message="Fifty rupees received",
            status=VoiceNotificationStatus.QUEUED.value,
        )
        db.add(notif)
        db.commit()

        with client.websocket_connect(f"/ws/device?token={token_a1}") as ws:
            # Consume replayed notification received on connect
            replayed = ws.receive_json()
            assert replayed["type"] == "voice_notification"

            ws.send_json({
                "type": "playback_ack",
                "notification_id": str(notif.id),
                "status": "FAILED",
                "error": "Speaker driver DAC buffer underrun",
            })
            resp = ws.receive_json()
            assert resp["type"] == "playback_ack_response"
            assert resp["status"] == VoiceNotificationStatus.FAILED.value

        db.expire_all()
        persisted = db.query(VoiceNotification).filter(VoiceNotification.id == notif.id).first()
        assert persisted.status == VoiceNotificationStatus.FAILED.value
        assert "Speaker driver DAC buffer underrun" in persisted.error_message
    finally:
        db.close()


def test_duplicate_played_ack_is_idempotent(client, playback_tenancy):
    """Multiple PLAYED ACKs for the same notification return DELIVERED idempotently."""
    token_a1 = playback_tenancy["token_a1"]
    device_a1 = playback_tenancy["device_a1"]
    merchant_a = playback_tenancy["merchant_a"]
    payment_a = playback_tenancy["payment_a"]

    db = PGTestSession()
    try:
        notif = VoiceNotification(
            id=uuid.uuid4(),
            merchant_id=merchant_a.id,
            device_id=device_a1.id,
            payment_id=payment_a.id,
            message="Fifty rupees received",
            status=VoiceNotificationStatus.QUEUED.value,
        )
        db.add(notif)
        db.commit()

        with client.websocket_connect(f"/ws/device?token={token_a1}") as ws:
            # Consume replayed notification received on connect
            replayed = ws.receive_json()
            assert replayed["type"] == "voice_notification"

            for _ in range(3):
                ws.send_json({
                    "type": "playback_ack",
                    "notification_id": str(notif.id),
                    "status": "PLAYED",
                })
                resp = ws.receive_json()
                assert resp["type"] == "playback_ack_response"
                assert resp["status"] == VoiceNotificationStatus.DELIVERED.value

        db.expire_all()
        persisted = db.query(VoiceNotification).filter(VoiceNotification.id == notif.id).first()
        assert persisted.status == VoiceNotificationStatus.DELIVERED.value
    finally:
        db.close()


def test_unauthorized_ack_cannot_modify_another_devices_notification(client, playback_tenancy):
    """Device A2 cannot ACK Device A1's notification; server responds with error and DB is untouched."""
    token_a2 = playback_tenancy["token_a2"]
    device_a1 = playback_tenancy["device_a1"]
    merchant_a = playback_tenancy["merchant_a"]
    payment_a = playback_tenancy["payment_a"]

    db = PGTestSession()
    try:
        notif_a1 = VoiceNotification(
            id=uuid.uuid4(),
            merchant_id=merchant_a.id,
            device_id=device_a1.id,
            payment_id=payment_a.id,
            message="Fifty rupees received",
            status=VoiceNotificationStatus.QUEUED.value,
        )
        db.add(notif_a1)
        db.commit()

        # Connect as Device A2 and attempt to ACK Device A1's notification
        with client.websocket_connect(f"/ws/device?token={token_a2}") as ws_a2:
            ws_a2.send_json({
                "type": "playback_ack",
                "notification_id": str(notif_a1.id),
                "status": "PLAYED",
            })
            resp = ws_a2.receive_json()
            assert resp["type"] == "error"
            assert "not authorized" in resp["detail"]

        # In DB, notification for Device A1 remains QUEUED
        db.expire_all()
        persisted = db.query(VoiceNotification).filter(VoiceNotification.id == notif_a1.id).first()
        assert persisted.status == VoiceNotificationStatus.QUEUED.value
        assert persisted.delivered_at is None
    finally:
        db.close()


def test_device_disconnect_does_not_mark_notification_as_played(client, playback_tenancy):
    """Disconnection before playback preserves QUEUED notification state."""
    token_a1 = playback_tenancy["token_a1"]
    device_a1 = playback_tenancy["device_a1"]
    merchant_a = playback_tenancy["merchant_a"]
    payment_a = playback_tenancy["payment_a"]

    db = PGTestSession()
    try:
        notif = VoiceNotification(
            id=uuid.uuid4(),
            merchant_id=merchant_a.id,
            device_id=device_a1.id,
            payment_id=payment_a.id,
            message="Fifty rupees received",
            status=VoiceNotificationStatus.QUEUED.value,
        )
        db.add(notif)
        db.commit()

        # Connect and abruptly disconnect
        with client.websocket_connect(f"/ws/device?token={token_a1}") as ws:
            replayed = ws.receive_json()
            assert replayed["type"] == "voice_notification"
            ws.send_text("ping")
            assert ws.receive_text() == "pong"

        # Notification state remains QUEUED
        db.expire_all()
        persisted = db.query(VoiceNotification).filter(VoiceNotification.id == notif.id).first()
        assert persisted.status == VoiceNotificationStatus.QUEUED.value
        assert persisted.delivered_at is None
    finally:
        db.close()


def test_payment_remains_unchanged_when_playback_fails(client, playback_tenancy):
    """Underlying financial Payment remains CAPTURED when playback fails (total ledger isolation)."""
    token_a1 = playback_tenancy["token_a1"]
    device_a1 = playback_tenancy["device_a1"]
    merchant_a = playback_tenancy["merchant_a"]
    payment_a = playback_tenancy["payment_a"]

    db = PGTestSession()
    try:
        notif = VoiceNotification(
            id=uuid.uuid4(),
            merchant_id=merchant_a.id,
            device_id=device_a1.id,
            payment_id=payment_a.id,
            message="Fifty rupees received",
            status=VoiceNotificationStatus.QUEUED.value,
        )
        db.add(notif)
        db.commit()

        # Send failure ACK
        with client.websocket_connect(f"/ws/device?token={token_a1}") as ws:
            replayed = ws.receive_json()
            assert replayed["type"] == "voice_notification"

            ws.send_json({
                "type": "playback_ack",
                "notification_id": str(notif.id),
                "status": "FAILED",
                "error": "Hardware speaker damaged",
            })
            resp = ws.receive_json()
            assert resp["status"] == VoiceNotificationStatus.FAILED.value

        # Verification: Notification is FAILED
        db.expire_all()
        persisted_notif = db.query(VoiceNotification).filter(VoiceNotification.id == notif.id).first()
        assert persisted_notif.status == VoiceNotificationStatus.FAILED.value

        # Crucial Verification: Financial Payment remains strictly CAPTURED!
        persisted_payment = db.query(Payment).filter(Payment.id == payment_a.id).first()
        assert persisted_payment.status == PaymentStatus.CAPTURED.value
        assert persisted_payment.amount_minor == 5000
    finally:
        db.close()
