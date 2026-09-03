"""
Phase 6.2 — Device WebSocket Bridge & Real-Time Event Dispatching Test Suite.

Verifies:
1. Valid Connection: Authenticated device session connects to /ws/device successfully; ping/pong works.
2. Missing Token: Unauthenticated connection attempt rejected with close code 1008.
3. Invalid / Expired Session: Invalid or expired session tokens rejected with close code 1008.
4. Inactive Device: Disabled or inactive device rejected with close code 1008.
5. Correct Event Delivery: Authenticated device receives its merchant's real-time payment event.
6. Strict Tenant Isolation: Device belonging to Merchant A never receives Merchant B's payment event.
7. Multi-Device Broadcast: Multiple active devices belonging to the same merchant concurrently receive events.
8. Malformed Event Safety: Malformed or mismatched event payloads are ignored safely without crashing socket.
9. Broken Connection Cleanup: Disconnected or broken device socket is pruned without disrupting peer devices.
10. Zero Provider Coupling: Device WebSocket and services contain zero imports of Razorpay SDK.
"""
from datetime import datetime, timezone, timedelta
import uuid
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.config import settings
from backend.app.models.merchant import Merchant
from backend.app.models.device import Device, DeviceStatus
from backend.app.models.device_session import DeviceSession, DeviceSessionStatus
from backend.app.services.device_service import device_service
from backend.app.services.websocket_manager import merchant_ws_manager

# Authoritative PostgreSQL connection for test fixture setup
pg_engine = create_engine(settings.DATABASE_URL)
PGTestSession = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def device_tenancy():
    """Create test merchants, provisioned devices, and active device sessions."""
    db = PGTestSession()
    cleanup_merchant_ids = []

    try:
        # Merchant A
        merchant_a = Merchant(
            id=uuid.uuid4(),
            name="Kirana A Supermarket",
            business_type="Retail",
            status="ACTIVE",
            currency="INR",
        )
        db.add(merchant_a)
        cleanup_merchant_ids.append(merchant_a.id)

        # Merchant B
        merchant_b = Merchant(
            id=uuid.uuid4(),
            name="Kirana B Hardware",
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
            device_name="A2 Floor Soundbox",
        )
        # Device B1 (Merchant B)
        device_b1, secret_b1 = device_service.register_device(
            db=db,
            merchant_id=merchant_b.id,
            device_name="B1 Checkout Soundbox",
        )

        db.flush()

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
            "token_a1": token_a1,
            "token_a2": token_a2,
            "token_b1": token_b1,
        }

    finally:
        db.query(DeviceSession).delete()
        db.query(Device).delete()
        db.query(Merchant).filter(Merchant.id.in_(cleanup_merchant_ids)).delete(synchronize_session=False)
        db.commit()
        db.close()


# =====================================================================
# 1. Device Handshake & Authentication Tests
# =====================================================================

def test_valid_device_session_connects_successfully(client, device_tenancy):
    """Authenticated Soundbox session connects to /ws/device; keepalive works."""
    token = device_tenancy["token_a1"]

    with client.websocket_connect(f"/ws/device?token={token}") as ws:
        ws.send_text("ping")
        assert ws.receive_text() == "pong"


def test_missing_device_session_rejected_with_1008(client):
    """Missing session token is rejected with policy violation close code 1008."""
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws/device"):
            pass
    assert exc.value.code == 1008


def test_invalid_device_session_rejected_with_1008(client):
    """Fabricated or malformed session token is rejected with code 1008."""
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws/device?token=devsess_completely_fabricated_token_12345"):
            pass
    assert exc.value.code == 1008


def test_expired_device_session_rejected_with_1008(client, device_tenancy):
    """Expired device session cannot connect; rejected with code 1008."""
    token = device_tenancy["token_a1"]
    dev_id = device_tenancy["device_a1"].id

    # Expire session in DB
    db = PGTestSession()
    try:
        sess = db.query(DeviceSession).filter(DeviceSession.device_id == dev_id).first()
        sess.expires_at = datetime.now(timezone.utc) - timedelta(hours=2)
        db.commit()
    finally:
        db.close()

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/ws/device?token={token}"):
            pass
    assert exc.value.code == 1008


def test_inactive_or_disabled_device_rejected_with_1008(client, device_tenancy):
    """Disabled device cannot connect even with a valid unexpired session."""
    token = device_tenancy["token_a1"]
    dev_id = device_tenancy["device_a1"].id

    # Mark device DISABLED
    db = PGTestSession()
    try:
        dev = db.query(Device).filter(Device.id == dev_id).first()
        dev.status = DeviceStatus.DISABLED.value
        db.commit()
    finally:
        db.close()

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/ws/device?token={token}"):
            pass
    assert exc.value.code == 1008


# =====================================================================
# 2. Event Delivery & Tenant Isolation Tests
# =====================================================================

@pytest.mark.asyncio
async def test_authenticated_device_receives_merchant_payment_event(client, device_tenancy):
    """Authenticated Soundbox receives real-time payment event published for its merchant."""
    token = device_tenancy["token_a1"]
    merchant_id = device_tenancy["merchant_a"].id

    with client.websocket_connect(f"/ws/device?token={token}") as ws:
        payload = {
            "event_id": str(uuid.uuid4()),
            "event_type": "payment.captured",
            "merchant_id": str(merchant_id),
            "payment_id": str(uuid.uuid4()),
            "provider": "RAZORPAY",
            "amount_minor": 150000,
            "currency": "INR",
            "status": "CAPTURED",
            "payment_method": "UPI",
            "payer_reference": "customer@upi",
        }

        # Broadcast via manager
        delivered = await merchant_ws_manager.broadcast_to_merchant(merchant_id, payload)
        assert delivered == 1

        received = ws.receive_json()
        assert received["event_id"] == payload["event_id"]
        assert received["amount_minor"] == 150000
        assert received["status"] == "CAPTURED"
        assert received["currency"] == "INR"


@pytest.mark.asyncio
async def test_device_cannot_receive_another_merchants_event(client, device_tenancy):
    """Soundbox of Merchant B never receives events destined for Merchant A."""
    token_b = device_tenancy["token_b1"]
    merchant_a_id = device_tenancy["merchant_a"].id
    merchant_b_id = device_tenancy["merchant_b"].id

    with client.websocket_connect(f"/ws/device?token={token_b}") as ws_b:
        payload_for_a = {
            "event_id": str(uuid.uuid4()),
            "event_type": "payment.captured",
            "merchant_id": str(merchant_a_id),
            "payment_id": str(uuid.uuid4()),
            "provider": "RAZORPAY",
            "amount_minor": 75000,
            "currency": "INR",
            "status": "CAPTURED",
        }

        # Deliver to Merchant A (Device B is on Merchant B)
        delivered = await merchant_ws_manager.broadcast_to_merchant(merchant_a_id, payload_for_a)
        assert delivered == 0

        # Verify Device B received nothing; ping/pong confirms connection is healthy
        ws_b.send_text("ping")
        assert ws_b.receive_text() == "pong"


@pytest.mark.asyncio
async def test_multiple_devices_for_same_merchant_receive_event(client, device_tenancy):
    """Multiple Soundbox devices under Merchant A all receive the broadcast concurrently."""
    token_a1 = device_tenancy["token_a1"]
    token_a2 = device_tenancy["token_a2"]
    merchant_id = device_tenancy["merchant_a"].id

    with client.websocket_connect(f"/ws/device?token={token_a1}") as ws_1:
        with client.websocket_connect(f"/ws/device?token={token_a2}") as ws_2:
            payload = {
                "event_id": str(uuid.uuid4()),
                "event_type": "payment.captured",
                "merchant_id": str(merchant_id),
                "payment_id": str(uuid.uuid4()),
                "amount_minor": 9900,
                "currency": "INR",
                "status": "CAPTURED",
            }

            delivered = await merchant_ws_manager.broadcast_to_merchant(merchant_id, payload)
            assert delivered == 2

            msg1 = ws_1.receive_json()
            msg2 = ws_2.receive_json()
            assert msg1["event_id"] == payload["event_id"]
            assert msg2["event_id"] == payload["event_id"]


@pytest.mark.asyncio
async def test_malformed_event_ignored_safely_by_device_bridge(client, device_tenancy):
    """Malformed or missing required fields in event are dropped safely without crashing device."""
    token = device_tenancy["token_a1"]
    merchant_id = device_tenancy["merchant_a"].id

    with client.websocket_connect(f"/ws/device?token={token}") as ws:
        # Malformed: missing payment_id
        malformed = {
            "event_id": str(uuid.uuid4()),
            "event_type": "payment.captured",
            "merchant_id": str(merchant_id),
        }

        delivered = await merchant_ws_manager.broadcast_to_merchant(merchant_id, malformed)
        assert delivered == 0

        # Verify device connection remains fully functional
        ws.send_text("ping")
        assert ws.receive_text() == "pong"


# =====================================================================
# 3. Resilience & Architectural Boundaries
# =====================================================================

@pytest.mark.asyncio
async def test_broken_device_connection_pruned_without_affecting_peers(client, device_tenancy):
    """Broken or disconnected device is cleaned up without impacting other connected devices."""
    from unittest.mock import AsyncMock
    merchant_id = device_tenancy["merchant_a"].id

    good_dev_ws = AsyncMock()
    bad_dev_ws = AsyncMock()
    bad_dev_ws.send_json.side_effect = RuntimeError("Hardware connection abruptly reset")

    # Enroll both under Merchant A
    await merchant_ws_manager.connect(merchant_id, good_dev_ws)
    await merchant_ws_manager.connect(merchant_id, bad_dev_ws)
    assert merchant_ws_manager.get_active_client_count(merchant_id) == 2

    payload = {
        "event_id": str(uuid.uuid4()),
        "event_type": "payment.captured",
        "merchant_id": str(merchant_id),
        "payment_id": str(uuid.uuid4()),
        "amount_minor": 45000,
        "currency": "INR",
        "status": "CAPTURED",
    }

    # Broadcast succeeds to healthy device
    delivered = await merchant_ws_manager.broadcast_to_merchant(merchant_id, payload)
    assert delivered == 1
    good_dev_ws.send_json.assert_awaited_once_with(payload)

    # Broken device was pruned automatically
    assert merchant_ws_manager.get_active_client_count(merchant_id) == 1

    # Cleanup
    await merchant_ws_manager.disconnect(merchant_id, good_dev_ws)
    assert merchant_ws_manager.get_active_client_count(merchant_id) == 0


def test_device_websocket_has_zero_razorpay_coupling():
    """Verify that device WebSocket and services contain zero imports of Razorpay SDK."""
    import inspect
    import backend.app.api.v1.websocket as ws_mod
    import backend.app.services.device_service as ds_mod
    import backend.app.services.websocket_manager as wm_mod

    for mod in (ws_mod, ds_mod, wm_mod):
        source = inspect.getsource(mod)
        assert "RazorpayClient" not in source
        assert "RazorpayProvider" not in source
        assert "backend.app.providers.razorpay" not in source
