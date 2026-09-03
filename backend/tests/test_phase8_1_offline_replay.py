"""
Phase 8.1 — Offline Device Notification Queuing & Replay Synchronization Test Suite.

Verifies:
1. Replay on Reconnect: Queued notification created while device was offline is replayed when device reconnects.
2. Delivered Notification Filtered: Previously DELIVERED notifications are never replayed.
3. Failed Notification Filtered: FAILED notifications are never replayed.
4. Scoped to Authenticated Device: Replay is strictly scoped to the authenticated device_id (Device 2 does not receive Device 1's queued notifications).
5. Cross-Merchant Rejection: Merchant B device cannot replay Merchant A notifications.
6. Oldest-First Ordering: Multiple queued notifications are replayed in deterministic chronological order (created_at ASC).
7. Disconnect Preservation: Disconnecting before sending playback ACK preserves QUEUED state for future reconnection.
8. PLAYED ACK after Replay: Replayed notification is marked DELIVERED when the device sends PLAYED ACK.
9. Duplicate ACK Idempotency: Multiple PLAYED ACKs after replay remain strictly idempotent.
10. Missing Audio Resilience: Corrupted or missing audio fails gracefully without crashing the active device WebSocket.
"""
from datetime import datetime, timezone, timedelta
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.config import settings
from backend.app.models.merchant import Merchant
from backend.app.models.device import Device
from backend.app.models.device_session import DeviceSession
from backend.app.models.payment import Payment, PaymentStatus
from backend.app.models.voice_notification import VoiceNotification, VoiceNotificationStatus
from backend.app.providers.tts.base import AudioResult
from backend.app.providers.tts.mock import MockTTSProvider
from backend.app.services.device_service import device_service
from backend.app.services.voice_notification_service import voice_notification_service

# Authoritative PostgreSQL connection for test fixture setup
pg_engine = create_engine(settings.DATABASE_URL)
PGTestSession = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def replay_tenancy():
    """Create test merchants, devices, payments, and active device sessions."""
    db = PGTestSession()
    cleanup_merchant_ids = []

    try:
        # Merchant A
        merchant_a = Merchant(
            id=uuid.uuid4(),
            name="Kirana A Super",
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
            device_name="A1 Main Soundbox",
        )
        # Device A2 (Merchant A)
        device_a2, secret_a2 = device_service.register_device(
            db=db,
            merchant_id=merchant_a.id,
            device_name="A2 Secondary Soundbox",
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
            amount_minor=5000,
            currency="INR",
            status=PaymentStatus.CAPTURED.value,
        )
        db.add(payment_a)

        # Authenticate device sessions
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
# 1. Offline Queuing & Replay Verification Tests
# =====================================================================

def test_queued_notification_is_replayed_when_device_reconnects(client, replay_tenancy):
    """Notification queued while device was offline is immediately replayed upon reconnection."""
    token_a1 = replay_tenancy["token_a1"]
    device_a1 = replay_tenancy["device_a1"]
    merchant_a = replay_tenancy["merchant_a"]
    payment_a = replay_tenancy["payment_a"]

    db = PGTestSession()
    try:
        # Create queued notification in PostgreSQL (Soundbox offline)
        notif = VoiceNotification(
            id=uuid.uuid4(),
            merchant_id=merchant_a.id,
            device_id=device_a1.id,
            payment_id=payment_a.id,
            message="Fifty rupees received",
            status=VoiceNotificationStatus.QUEUED.value,
            attempt_count=0,
            created_at=datetime.now(timezone.utc),
        )
        db.add(notif)
        db.commit()

        # Device connects to /ws/device
        with client.websocket_connect(f"/ws/device?token={token_a1}") as ws:
            # Device immediately receives replayed offline notification
            msg = ws.receive_json()
            assert msg["type"] == "voice_notification"
            assert msg["notification_id"] == str(notif.id)
            assert msg["device_id"] == str(device_a1.id)
            assert msg["text"] == "Fifty rupees received"
            assert "audio_data" in msg
            assert msg["audio_content_type"] == "audio/wav"

            # Ping/pong still works normally
            ws.send_text("ping")
            assert ws.receive_text() == "pong"
    finally:
        db.close()


def test_delivered_notification_is_not_replayed(client, replay_tenancy):
    """Notifications already in DELIVERED state are never replayed upon reconnection."""
    token_a1 = replay_tenancy["token_a1"]
    device_a1 = replay_tenancy["device_a1"]
    merchant_a = replay_tenancy["merchant_a"]
    payment_a = replay_tenancy["payment_a"]

    db = PGTestSession()
    try:
        notif = VoiceNotification(
            id=uuid.uuid4(),
            merchant_id=merchant_a.id,
            device_id=device_a1.id,
            payment_id=payment_a.id,
            message="Fifty rupees received",
            status=VoiceNotificationStatus.DELIVERED.value,
            delivered_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        db.add(notif)
        db.commit()

        with client.websocket_connect(f"/ws/device?token={token_a1}") as ws:
            # Should NOT receive any replay message; ping/pong responds immediately
            ws.send_text("ping")
            assert ws.receive_text() == "pong"
    finally:
        db.close()


def test_failed_notification_is_not_replayed(client, replay_tenancy):
    """Notifications in FAILED state are never replayed upon reconnection."""
    token_a1 = replay_tenancy["token_a1"]
    device_a1 = replay_tenancy["device_a1"]
    merchant_a = replay_tenancy["merchant_a"]
    payment_a = replay_tenancy["payment_a"]

    db = PGTestSession()
    try:
        notif = VoiceNotification(
            id=uuid.uuid4(),
            merchant_id=merchant_a.id,
            device_id=device_a1.id,
            payment_id=payment_a.id,
            message="Fifty rupees received",
            status=VoiceNotificationStatus.FAILED.value,
            error_message="Hardware failure",
            created_at=datetime.now(timezone.utc),
        )
        db.add(notif)
        db.commit()

        with client.websocket_connect(f"/ws/device?token={token_a1}") as ws:
            ws.send_text("ping")
            assert ws.receive_text() == "pong"
    finally:
        db.close()


def test_replay_is_scoped_to_authenticated_device(client, replay_tenancy):
    """Device A2 does NOT receive queued notifications intended for Device A1."""
    token_a2 = replay_tenancy["token_a2"]
    device_a1 = replay_tenancy["device_a1"]
    merchant_a = replay_tenancy["merchant_a"]
    payment_a = replay_tenancy["payment_a"]

    db = PGTestSession()
    try:
        # Queued for Device A1
        notif = VoiceNotification(
            id=uuid.uuid4(),
            merchant_id=merchant_a.id,
            device_id=device_a1.id,
            payment_id=payment_a.id,
            message="Fifty rupees received",
            status=VoiceNotificationStatus.QUEUED.value,
            created_at=datetime.now(timezone.utc),
        )
        db.add(notif)
        db.commit()

        # Connect as Device A2
        with client.websocket_connect(f"/ws/device?token={token_a2}") as ws_a2:
            # Device A2 should not receive Device A1's notification
            ws_a2.send_text("ping")
            assert ws_a2.receive_text() == "pong"
    finally:
        db.close()


def test_cross_merchant_notification_cannot_be_replayed(client, replay_tenancy):
    """Device B1 (Merchant B) never receives queued notifications from Merchant A."""
    token_b1 = replay_tenancy["token_b1"]
    device_a1 = replay_tenancy["device_a1"]
    merchant_a = replay_tenancy["merchant_a"]
    payment_a = replay_tenancy["payment_a"]

    db = PGTestSession()
    try:
        notif = VoiceNotification(
            id=uuid.uuid4(),
            merchant_id=merchant_a.id,
            device_id=device_a1.id,
            payment_id=payment_a.id,
            message="Fifty rupees received",
            status=VoiceNotificationStatus.QUEUED.value,
            created_at=datetime.now(timezone.utc),
        )
        db.add(notif)
        db.commit()

        with client.websocket_connect(f"/ws/device?token={token_b1}") as ws_b1:
            ws_b1.send_text("ping")
            assert ws_b1.receive_text() == "pong"
    finally:
        db.close()


def test_multiple_queued_notifications_replay_oldest_first(client, replay_tenancy):
    """Multiple queued notifications are replayed in deterministic chronological order (created_at ASC)."""
    token_a1 = replay_tenancy["token_a1"]
    device_a1 = replay_tenancy["device_a1"]
    merchant_a = replay_tenancy["merchant_a"]
    payment_a = replay_tenancy["payment_a"]

    db = PGTestSession()
    try:
        now = datetime.now(timezone.utc)
        # Create 3 notifications with distinct staggered timestamps
        notif_old = VoiceNotification(
            id=uuid.uuid4(),
            merchant_id=merchant_a.id,
            device_id=device_a1.id,
            payment_id=payment_a.id,
            message="First notification",
            status=VoiceNotificationStatus.QUEUED.value,
            created_at=now - timedelta(seconds=30),
        )
        notif_mid = VoiceNotification(
            id=uuid.uuid4(),
            merchant_id=merchant_a.id,
            device_id=device_a1.id,
            payment_id=payment_a.id,
            message="Second notification",
            status=VoiceNotificationStatus.QUEUED.value,
            created_at=now - timedelta(seconds=20),
        )
        notif_new = VoiceNotification(
            id=uuid.uuid4(),
            merchant_id=merchant_a.id,
            device_id=device_a1.id,
            payment_id=payment_a.id,
            message="Third notification",
            status=VoiceNotificationStatus.QUEUED.value,
            created_at=now - timedelta(seconds=10),
        )
        db.add_all([notif_mid, notif_new, notif_old])  # Insert out of order
        db.commit()

        with client.websocket_connect(f"/ws/device?token={token_a1}") as ws:
            # Verify oldest-first replay order
            msg1 = ws.receive_json()
            assert msg1["text"] == "First notification"
            assert msg1["notification_id"] == str(notif_old.id)

            msg2 = ws.receive_json()
            assert msg2["text"] == "Second notification"
            assert msg2["notification_id"] == str(notif_mid.id)

            msg3 = ws.receive_json()
            assert msg3["text"] == "Third notification"
            assert msg3["notification_id"] == str(notif_new.id)
    finally:
        db.close()


def test_device_disconnect_before_ack_leaves_notification_eligible(client, replay_tenancy):
    """Disconnecting before sending PLAYED ACK leaves notification eligible for next reconnect."""
    token_a1 = replay_tenancy["token_a1"]
    device_a1 = replay_tenancy["device_a1"]
    merchant_a = replay_tenancy["merchant_a"]
    payment_a = replay_tenancy["payment_a"]

    db = PGTestSession()
    try:
        notif = VoiceNotification(
            id=uuid.uuid4(),
            merchant_id=merchant_a.id,
            device_id=device_a1.id,
            payment_id=payment_a.id,
            message="Fifty rupees received",
            status=VoiceNotificationStatus.QUEUED.value,
            created_at=datetime.now(timezone.utc),
        )
        db.add(notif)
        db.commit()

        # Session 1: Connects, receives notification, abruptly disconnects without ACK
        with client.websocket_connect(f"/ws/device?token={token_a1}") as ws:
            msg = ws.receive_json()
            assert msg["notification_id"] == str(notif.id)

        # In DB, status remains QUEUED
        db.expire_all()
        persisted = db.query(VoiceNotification).filter(VoiceNotification.id == notif.id).first()
        assert persisted.status == VoiceNotificationStatus.QUEUED.value
        assert persisted.delivered_at is None

        # Session 2: Reconnects -> notification is replayed again!
        with client.websocket_connect(f"/ws/device?token={token_a1}") as ws2:
            msg2 = ws2.receive_json()
            assert msg2["notification_id"] == str(notif.id)
            assert msg2["text"] == "Fifty rupees received"
    finally:
        db.close()


def test_played_ack_after_replay_marks_notification_delivered(client, replay_tenancy):
    """Sending PLAYED ACK after offline replay successfully transitions notification to DELIVERED."""
    token_a1 = replay_tenancy["token_a1"]
    device_a1 = replay_tenancy["device_a1"]
    merchant_a = replay_tenancy["merchant_a"]
    payment_a = replay_tenancy["payment_a"]

    db = PGTestSession()
    try:
        notif = VoiceNotification(
            id=uuid.uuid4(),
            merchant_id=merchant_a.id,
            device_id=device_a1.id,
            payment_id=payment_a.id,
            message="Fifty rupees received",
            status=VoiceNotificationStatus.QUEUED.value,
            created_at=datetime.now(timezone.utc),
        )
        db.add(notif)
        db.commit()

        with client.websocket_connect(f"/ws/device?token={token_a1}") as ws:
            msg = ws.receive_json()
            assert msg["notification_id"] == str(notif.id)

            # Send PLAYED ACK
            ws.send_json({
                "type": "playback_ack",
                "notification_id": str(notif.id),
                "status": "PLAYED",
            })
            resp = ws.receive_json()
            assert resp["type"] == "playback_ack_response"
            assert resp["status"] == VoiceNotificationStatus.DELIVERED.value

        # Verify in DB
        db.expire_all()
        persisted = db.query(VoiceNotification).filter(VoiceNotification.id == notif.id).first()
        assert persisted.status == VoiceNotificationStatus.DELIVERED.value
        assert persisted.delivered_at is not None
    finally:
        db.close()


def test_duplicate_played_ack_after_replay_remains_idempotent(client, replay_tenancy):
    """Multiple PLAYED ACKs after replay produce idempotent responses with zero database corruption."""
    token_a1 = replay_tenancy["token_a1"]
    device_a1 = replay_tenancy["device_a1"]
    merchant_a = replay_tenancy["merchant_a"]
    payment_a = replay_tenancy["payment_a"]

    db = PGTestSession()
    try:
        notif = VoiceNotification(
            id=uuid.uuid4(),
            merchant_id=merchant_a.id,
            device_id=device_a1.id,
            payment_id=payment_a.id,
            message="Fifty rupees received",
            status=VoiceNotificationStatus.QUEUED.value,
            created_at=datetime.now(timezone.utc),
        )
        db.add(notif)
        db.commit()

        with client.websocket_connect(f"/ws/device?token={token_a1}") as ws:
            ws.receive_json()  # Consume replayed message

            for _ in range(3):
                ws.send_json({
                    "type": "playback_ack",
                    "notification_id": str(notif.id),
                    "status": "PLAYED",
                })
                resp = ws.receive_json()
                assert resp["status"] == VoiceNotificationStatus.DELIVERED.value

        db.expire_all()
        persisted = db.query(VoiceNotification).filter(VoiceNotification.id == notif.id).first()
        assert persisted.status == VoiceNotificationStatus.DELIVERED.value
    finally:
        db.close()


def test_missing_audio_does_not_crash_device_websocket(client, replay_tenancy):
    """If audio synthesis fails during replay, the device WebSocket remains healthy and alive."""
    token_a1 = replay_tenancy["token_a1"]
    device_a1 = replay_tenancy["device_a1"]
    merchant_a = replay_tenancy["merchant_a"]
    payment_a = replay_tenancy["payment_a"]

    db = PGTestSession()
    try:
        # Empty message which fails synthesis
        notif = VoiceNotification(
            id=uuid.uuid4(),
            merchant_id=merchant_a.id,
            device_id=device_a1.id,
            payment_id=payment_a.id,
            message="   ",  # Invalid empty text triggers MockTTSProvider ValueError
            status=VoiceNotificationStatus.QUEUED.value,
            created_at=datetime.now(timezone.utc),
        )
        db.add(notif)
        db.commit()

        with client.websocket_connect(f"/ws/device?token={token_a1}") as ws:
            # WebSocket should remain open and responsive despite unplayable notification
            ws.send_text("ping")
            assert ws.receive_text() == "pong"

        # Notification state remains QUEUED (not crashed, not marked DELIVERED)
        db.expire_all()
        persisted = db.query(VoiceNotification).filter(VoiceNotification.id == notif.id).first()
        assert persisted.status == VoiceNotificationStatus.QUEUED.value
    finally:
        db.close()
