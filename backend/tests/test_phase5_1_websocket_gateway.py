"""
Phase 5.1 — Minimal Real-Time WebSocket Gateway Test Suite.

Verifies:
1. Valid Authentication: Valid JWT connects successfully and establishes WebSocket session.
2. Invalid Authentication: Missing, invalid, or expired JWT rejected with close code 1008.
3. Merchant Authorization: User not belonging to requested merchant rejected with 1008.
4. Correct Event Delivery: Merchant A receives valid payment event for Merchant A.
5. Strict Tenant Isolation: Merchant B does not receive Merchant A's payment event.
6. Multiple Clients: Multiple concurrent clients for the same merchant both receive event.
7. Malformed Event Handling: Malformed or mismatched Redis event is safely ignored without crash.
8. Client Disconnect Cleanup: Broken or disconnected client is cleaned up without affecting peers.
"""
from datetime import timedelta
import uuid
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.config import settings
from backend.app.models.user import User
from backend.app.models.merchant import Merchant
from backend.app.models.merchant_user import MerchantUser
from backend.app.core.security import create_access_token, hash_password
from backend.app.services.websocket_manager import merchant_ws_manager, validate_event_payload

# Authoritative PostgreSQL connection for test data setup
pg_engine = create_engine(settings.DATABASE_URL)
PGTestSession = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def test_tenancy():
    """Create test merchants, users, and memberships committed to PostgreSQL."""
    db = PGTestSession()
    cleanup_user_ids = []
    cleanup_merchant_ids = []

    try:
        # Merchant A
        merchant_a = Merchant(
            id=uuid.uuid4(),
            name="WebSocket Test Kirana A",
            business_type="Retail",
            status="ACTIVE",
            currency="INR",
        )
        db.add(merchant_a)
        cleanup_merchant_ids.append(merchant_a.id)

        # Merchant B
        merchant_b = Merchant(
            id=uuid.uuid4(),
            name="WebSocket Test Kirana B",
            business_type="Retail",
            status="ACTIVE",
            currency="INR",
        )
        db.add(merchant_b)
        cleanup_merchant_ids.append(merchant_b.id)

        # User A (belongs to Merchant A only)
        user_a = User(
            id=uuid.uuid4(),
            email=f"usera_{uuid.uuid4().hex[:6]}@example.com",
            hashed_password=hash_password("ValidPassword123!"),
            is_active=True,
        )
        db.add(user_a)
        cleanup_user_ids.append(user_a.id)

        # User B (belongs to Merchant B only)
        user_b = User(
            id=uuid.uuid4(),
            email=f"userb_{uuid.uuid4().hex[:6]}@example.com",
            hashed_password=hash_password("ValidPassword123!"),
            is_active=True,
        )
        db.add(user_b)
        cleanup_user_ids.append(user_b.id)

        db.flush()

        # Memberships
        m_user_a = MerchantUser(
            id=uuid.uuid4(),
            merchant_id=merchant_a.id,
            user_id=user_a.id,
            role="OWNER",
        )
        m_user_b = MerchantUser(
            id=uuid.uuid4(),
            merchant_id=merchant_b.id,
            user_id=user_b.id,
            role="OWNER",
        )
        db.add(m_user_a)
        db.add(m_user_b)
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
        db.query(MerchantUser).filter(MerchantUser.user_id.in_(cleanup_user_ids)).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_(cleanup_user_ids)).delete(synchronize_session=False)
        db.query(Merchant).filter(Merchant.id.in_(cleanup_merchant_ids)).delete(synchronize_session=False)
        db.commit()
        db.close()


# =====================================================================
# 1. Authentication Tests
# =====================================================================

def test_valid_jwt_connects_successfully(client, test_tenancy):
    """Valid JWT establishes WebSocket connection; ping/pong works."""
    token = test_tenancy["token_a"]
    merchant_id = test_tenancy["merchant_a"].id

    with client.websocket_connect(f"/ws/merchant?token={token}&merchant_id={merchant_id}") as ws:
        ws.send_text("ping")
        assert ws.receive_text() == "pong"


def test_missing_jwt_rejected_with_1008(client):
    """Missing JWT is rejected immediately with policy violation close code 1008."""
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws/merchant"):
            pass
    assert exc.value.code == 1008


def test_invalid_and_expired_jwt_rejected_with_1008(client, test_tenancy):
    """Invalid signature and expired token are rejected with code 1008."""
    # Invalid token
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws/merchant?token=invalid.jwt.token"):
            pass
    assert exc.value.code == 1008

    # Expired token
    user = test_tenancy["user_a"]
    expired_token = create_access_token(
        user_id=user.id,
        email=user.email,
        expires_delta=timedelta(seconds=-10),
    )
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/ws/merchant?token={expired_token}"):
            pass
    assert exc.value.code == 1008


# =====================================================================
# 2. Authorization & Tenant Isolation Tests
# =====================================================================

def test_unauthorized_merchant_rejected_with_1008(client, test_tenancy):
    """User A attempting to connect to Merchant B's channel is rejected with code 1008."""
    token_a = test_tenancy["token_a"]
    merchant_b_id = test_tenancy["merchant_b"].id

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/ws/merchant?token={token_a}&merchant_id={merchant_b_id}") as ws:
            ws.send_text("ping")
    assert exc.value.code == 1008


@pytest.mark.asyncio
async def test_correct_event_delivery_to_authorized_client(client, test_tenancy):
    """Authorized merchant client receives matching payment event."""
    token = test_tenancy["token_a"]
    merchant_id = test_tenancy["merchant_a"].id

    with client.websocket_connect(f"/ws/merchant?token={token}&merchant_id={merchant_id}") as ws:
        payload = {
            "event_id": str(uuid.uuid4()),
            "event_type": "payment.captured",
            "merchant_id": str(merchant_id),
            "payment_id": str(uuid.uuid4()),
            "amount_minor": 50000,
            "currency": "INR",
            "status": "CAPTURED",
        }

        # Broadcast via manager directly
        delivered = await merchant_ws_manager.broadcast_to_merchant(merchant_id, payload)
        assert delivered == 1

        received = ws.receive_json()
        assert received["event_id"] == payload["event_id"]
        assert received["amount_minor"] == 50000
        assert received["status"] == "CAPTURED"


@pytest.mark.asyncio
async def test_strict_tenant_isolation_cross_merchant(client, test_tenancy):
    """Merchant B never receives events destined for Merchant A."""
    token_b = test_tenancy["token_b"]
    merchant_a_id = test_tenancy["merchant_a"].id
    merchant_b_id = test_tenancy["merchant_b"].id

    with client.websocket_connect(f"/ws/merchant?token={token_b}&merchant_id={merchant_b_id}") as ws_b:
        payload_for_a = {
            "event_id": str(uuid.uuid4()),
            "event_type": "payment.captured",
            "merchant_id": str(merchant_a_id),
            "payment_id": str(uuid.uuid4()),
            "amount_minor": 120000,
            "currency": "INR",
            "status": "CAPTURED",
        }

        # Deliver to Merchant A (Merchant B has no clients on A)
        delivered = await merchant_ws_manager.broadcast_to_merchant(merchant_a_id, payload_for_a)
        assert delivered == 0

        # Verify Client B receives nothing; ping/pong confirms connection is unaffected
        ws_b.send_text("ping")
        assert ws_b.receive_text() == "pong"


# =====================================================================
# 3. Multiple Clients & Resilience
# =====================================================================

@pytest.mark.asyncio
async def test_multiple_clients_for_same_merchant_receive_event(client, test_tenancy):
    """Two concurrent clients for Merchant A both receive the broadcast event."""
    token = test_tenancy["token_a"]
    merchant_id = test_tenancy["merchant_a"].id

    with client.websocket_connect(f"/ws/merchant?token={token}&merchant_id={merchant_id}") as ws1:
        with client.websocket_connect(f"/ws/merchant?token={token}&merchant_id={merchant_id}") as ws2:
            assert merchant_ws_manager.get_active_client_count(merchant_id) == 2

            payload = {
                "event_id": str(uuid.uuid4()),
                "event_type": "payment.captured",
                "merchant_id": str(merchant_id),
                "payment_id": str(uuid.uuid4()),
                "amount_minor": 75000,
                "currency": "INR",
                "status": "CAPTURED",
            }

            delivered = await merchant_ws_manager.broadcast_to_merchant(merchant_id, payload)
            assert delivered == 2

            msg1 = ws1.receive_json()
            msg2 = ws2.receive_json()
            assert msg1["event_id"] == payload["event_id"]
            assert msg2["event_id"] == payload["event_id"]


@pytest.mark.asyncio
async def test_malformed_event_ignored_safely(client, test_tenancy):
    """Malformed or missing required fields are safely rejected without crashing server."""
    merchant_id = test_tenancy["merchant_a"].id

    # Non-dict
    assert validate_event_payload("not-a-dict", merchant_id) is None
    # Missing required keys
    assert validate_event_payload({"event_id": "123"}, merchant_id) is None
    # Mismatched merchant
    assert validate_event_payload(
        {"event_id": "1", "event_type": "pay", "merchant_id": str(uuid.uuid4()), "payment_id": "p"},
        merchant_id,
    ) is None


@pytest.mark.asyncio
async def test_broken_client_cleanup_without_affecting_peers(test_tenancy):
    """A broken client raising an exception during send is disconnected without affecting healthy peers."""
    from unittest.mock import AsyncMock
    merchant_id = test_tenancy["merchant_a"].id

    # Create one healthy mock websocket and one failing mock websocket
    good_ws = AsyncMock()
    bad_ws = AsyncMock()
    bad_ws.send_json.side_effect = RuntimeError("Socket connection abruptly reset")

    # Manually register both in manager
    await merchant_ws_manager.connect(merchant_id, good_ws)
    await merchant_ws_manager.connect(merchant_id, bad_ws)
    assert merchant_ws_manager.get_active_client_count(merchant_id) == 2

    payload = {
        "event_id": str(uuid.uuid4()),
        "event_type": "payment.captured",
        "merchant_id": str(merchant_id),
        "payment_id": str(uuid.uuid4()),
    }

    delivered = await merchant_ws_manager.broadcast_to_merchant(merchant_id, payload)
    # Healthy client got the message
    assert delivered == 1
    good_ws.send_json.assert_awaited_once_with(payload)

    # Broken client was pruned automatically
    assert merchant_ws_manager.get_active_client_count(merchant_id) == 1

    # Cleanup remaining good_ws
    await merchant_ws_manager.disconnect(merchant_id, good_ws)
    assert merchant_ws_manager.get_active_client_count(merchant_id) == 0


def test_core_websocket_has_zero_razorpay_coupling():
    """Verify WebSocket manager and endpoint do NOT import Razorpay SDK/client."""
    import inspect
    import backend.app.services.websocket_manager as mgr_mod
    import backend.app.api.v1.websocket as ep_mod

    for mod in (mgr_mod, ep_mod):
        source = inspect.getsource(mod)
        assert "RazorpayClient" not in source
        assert "RazorpayProvider" not in source
        assert "backend.app.providers.razorpay" not in source
