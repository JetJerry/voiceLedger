"""
VoiceLedger Real-Time WebSocket Gateway Endpoint (API v1).

Provides an authenticated WebSocket endpoint for merchant clients to receive
real-time payment and notification events over the Redis event bus.

Path:
    /ws/merchant

Security & Invariants:
1. Authentication: Enforces standard JWT access token validation (via query param or header).
2. Authorization & RBAC: Verifies that the authenticated user is an active member of the
   requested merchant organization.
3. Strict Tenant Isolation: Subscribes only to the authorized merchant's channel.
4. Non-Blocking: Database sessions are opened only for handshake verification and immediately
   closed before the persistent connection loop begins.
5. Zero Financial Mutation: Cannot mutate payments, events, or balances.
"""
import json
import logging
from typing import Optional
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from sqlalchemy.orm import Session

from backend.app.db.session import SessionLocal
from backend.app.models.user import User
from backend.app.models.merchant import Merchant
from backend.app.models.merchant_user import MerchantUser
from backend.app.core.security import (
    decode_access_token,
    TokenExpiredError,
    InvalidTokenError,
)
from backend.app.services.websocket_manager import merchant_ws_manager
from backend.app.services.device_service import (
    device_service,
    DeviceInactiveError,
    DeviceSessionInvalidError,
    DeviceNotFoundError,
)
from backend.app.services.voice_notification_service import (
    voice_notification_service,
    VoiceNotificationNotFoundError,
    VoiceNotificationForbiddenError,
)

logger = logging.getLogger("voiceledger.websocket.endpoint")

router = APIRouter(tags=["WebSocket Gateway"])


@router.websocket("/ws/merchant")
async def merchant_websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    merchant_id: Optional[str] = Query(None),
):
    """
    Real-time payment event streaming endpoint for authenticated merchant clients.

    Handshake:
    1. Authenticate Bearer JWT from query param `?token=` or Authorization header.
    2. Authorize tenant access against MerchantUser membership in PostgreSQL.
    3. Accept connection and bind to tenant Redis Pub/Sub stream.
    """
    # 1. Extract Token (Query parameter preferred for WebSockets, fallback to Authorization header)
    auth_token = token
    if not auth_token:
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            auth_token = auth_header[7:].strip()

    if not auth_token:
        logger.warning("Rejected WebSocket connection: missing authentication token")
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Missing authentication token",
        )
        return

    # 2. Cryptographic JWT Verification
    try:
        payload = decode_access_token(auth_token)
    except TokenExpiredError:
        logger.warning("Rejected WebSocket connection: token has expired")
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Token has expired",
        )
        return
    except (InvalidTokenError, Exception) as exc:
        logger.warning("Rejected WebSocket connection: invalid token (%s)", exc)
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Invalid authentication token",
        )
        return

    user_id_str = payload.get("sub")
    if not user_id_str:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Invalid token payload",
        )
        return

    try:
        user_uuid = uuid.UUID(str(user_id_str))
    except (ValueError, TypeError):
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Invalid user identifier",
        )
        return

    # 3. User & Merchant Authorization check against PostgreSQL
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_uuid).first()
        if not user or not user.is_active:
            logger.warning("Rejected WebSocket: user %s not found or inactive", user_uuid)
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Account is inactive or not found",
            )
            return

        # Resolve target merchant
        target_merchant_uuid: Optional[uuid.UUID] = None
        raw_merchant_id = merchant_id or websocket.headers.get("x-merchant-id")
        if raw_merchant_id:
            try:
                target_merchant_uuid = uuid.UUID(str(raw_merchant_id).strip())
            except (ValueError, TypeError):
                await websocket.close(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason="Invalid merchant_id format",
                )
                return

        if target_merchant_uuid is None:
            memberships = (
                db.query(MerchantUser)
                .filter(MerchantUser.user_id == user.id)
                .all()
            )
            if len(memberships) == 0:
                await websocket.close(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason="User does not belong to any merchant organization",
                )
                return
            if len(memberships) > 1:
                await websocket.close(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason="Multiple merchant memberships found. Please specify merchant_id",
                )
                return
            target_merchant_uuid = memberships[0].merchant_id

        # Verify active membership
        membership = (
            db.query(MerchantUser)
            .join(Merchant, MerchantUser.merchant_id == Merchant.id)
            .filter(
                MerchantUser.user_id == user.id,
                MerchantUser.merchant_id == target_merchant_uuid,
            )
            .first()
        )

        if not membership:
            logger.warning("Rejected WebSocket: user %s is not member of merchant %s", user.id, target_merchant_uuid)
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Forbidden: User is not a member of the requested merchant",
            )
            return

        if membership.merchant.status != "ACTIVE":
            logger.warning("Rejected WebSocket: merchant %s is not ACTIVE", target_merchant_uuid)
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Forbidden: Merchant organization is not active",
            )
            return

    finally:
        # Crucial: DB session is closed immediately after handshake validation.
        # It is never held open during persistent WebSocket streaming.
        db.close()

    # 4. Accept WebSocket connection and register with connection manager
    await websocket.accept()
    await merchant_ws_manager.connect(target_merchant_uuid, websocket)

    try:
        while True:
            # Keep connection open; handle client keep-alive pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        logger.info("Client disconnected normally for merchant %s", target_merchant_uuid)
    except Exception as exc:
        logger.warning("WebSocket exception for merchant %s: %s", target_merchant_uuid, exc)
    finally:
        await merchant_ws_manager.disconnect(target_merchant_uuid, websocket)


@router.websocket("/ws/device")
async def device_websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
):
    """
    Real-time payment event streaming endpoint for authenticated Soundbox devices.

    Handshake:
    1. Extract session token from query param ?token=, X-Device-Session-Token header,
       or Authorization: Bearer <devsess_...> header.
    2. Validate session token hash, active status, unexpired state, and active parent device
       against PostgreSQL via device_service.verify_device_session.
    3. Derives target merchant strictly from device.merchant_id.
    4. Accept connection and enroll with merchant_ws_manager for real-time Redis streaming.
    """
    auth_token = token
    if not auth_token:
        auth_token = websocket.headers.get("x-device-session-token")
    if not auth_token:
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            auth_token = auth_header[7:].strip()

    if not auth_token:
        logger.warning("Rejected Device WebSocket: missing session token")
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Missing device session token",
        )
        return

    # Verify session & resolve merchant
    db: Session = SessionLocal()
    try:
        device, session = device_service.verify_device_session(
            db=db,
            raw_session_token=auth_token,
        )
        target_merchant_id = device.merchant_id
        device_id = device.id
        db.commit()
    except (DeviceSessionInvalidError, DeviceNotFoundError) as exc:
        db.rollback()
        logger.warning("Rejected Device WebSocket: invalid session (%s)", exc)
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Invalid or expired device session",
        )
        return
    except DeviceInactiveError as exc:
        db.rollback()
        logger.warning("Rejected Device WebSocket: inactive device (%s)", exc)
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Device is inactive or disabled",
        )
        return
    except Exception as exc:
        db.rollback()
        logger.error("Unexpected error during device WebSocket handshake: %s", exc)
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Device authentication failed",
        )
        return
    finally:
        db.close()

    # Accept connection and register under the merchant with device_id
    await websocket.accept()
    await merchant_ws_manager.connect(target_merchant_id, websocket, device_id=device_id)
    logger.info("Device %s connected for merchant %s", device_id, target_merchant_id)

    # Replay any pending unacknowledged voice notifications for this reconnecting device
    db_replay: Session = SessionLocal()
    try:
        replayed = await voice_notification_service.replay_pending_notifications_for_device(
            db=db_replay,
            device_id=device_id,
        )
        if replayed > 0:
            logger.info("Replayed %d pending voice notifications for device %s", replayed, device_id)
    except Exception as exc:
        logger.error("Error during offline replay for device %s: %s", device_id, exc)
    finally:
        db_replay.close()

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
                continue

            try:
                msg = json.loads(data)
            except Exception:
                continue

            if isinstance(msg, dict) and msg.get("type") == "playback_ack":
                notif_id_str = msg.get("notification_id")
                ack_status = msg.get("status", "PLAYED")
                if not notif_id_str:
                    await websocket.send_json({"type": "error", "detail": "Missing notification_id"})
                    continue

                try:
                    notif_uuid = uuid.UUID(str(notif_id_str))
                except (ValueError, TypeError):
                    await websocket.send_json({"type": "error", "detail": "Invalid notification_id format"})
                    continue

                db_sess: Session = SessionLocal()
                try:
                    updated = voice_notification_service.record_playback_ack(
                        db=db_sess,
                        device_id=device_id,
                        notification_id=notif_uuid,
                        ack_status=ack_status,
                        error_detail=msg.get("error"),
                    )
                    await websocket.send_json({
                        "type": "playback_ack_response",
                        "notification_id": str(updated.id),
                        "status": updated.status,
                    })
                except VoiceNotificationForbiddenError as exc:
                    await websocket.send_json({"type": "error", "detail": str(exc)})
                except VoiceNotificationNotFoundError as exc:
                    await websocket.send_json({"type": "error", "detail": str(exc)})
                except Exception as exc:
                    logger.error("Error processing playback ACK from device %s: %s", device_id, exc)
                    await websocket.send_json({"type": "error", "detail": "Failed to process playback ACK"})
                finally:
                    db_sess.close()

    except WebSocketDisconnect:
        logger.info("Device %s disconnected normally", device_id)
    except Exception as exc:
        logger.warning("Device %s WebSocket exception: %s", device_id, exc)
    finally:
        await merchant_ws_manager.disconnect(target_merchant_id, websocket)
