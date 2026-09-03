"""
VoiceLedger WebSocket Connection Manager.

Manages active real-time WebSocket connections partitioned by merchant organization.
Subscribes to tenant-specific Redis Pub/Sub channels (voiceledger:merchant:{id}:events)
and broadcasts validated, sanitized payment events to authenticated client connections.

Invariants:
1. Strict Tenant Partitioning: Merchant A connections ONLY receive Merchant A events.
2. In-Process Connection Tracking: Maps merchant_id -> Set[WebSocket].
3. Dynamic Subscription: Subscribes to Redis channel only when >= 1 connection exists;
   unsubscribes and cleans up task when connection count drops to 0.
4. Resilience: One broken WebSocket client disconnects cleanly without affecting peers.
5. Payload Validation: Validates presence of event_id, event_type, merchant_id, payment_id
   and strict merchant matching before client transmission.
6. Zero Financial Mutation: Strictly a real-time event transport; never alters database state.
"""
import asyncio
from collections import defaultdict
import json
import logging
from typing import Dict, Set, Optional, Any, Callable
import uuid

from fastapi import WebSocket
from redis.exceptions import RedisError

from backend.app.core.redis import get_redis_client

logger = logging.getLogger("voiceledger.websocket.manager")


def validate_event_payload(payload: Any, expected_merchant_id: uuid.UUID) -> Optional[Dict[str, Any]]:
    """
    Validate that an incoming event dictionary has the required fields and matches
    the expected merchant identifier.
    """
    if not isinstance(payload, dict):
        logger.warning("Rejected non-dict WebSocket message: %r", payload)
        return None

    required_fields = ("event_id", "event_type", "merchant_id", "payment_id")
    for field in required_fields:
        if not payload.get(field):
            logger.warning("Rejected event missing required field '%s': %r", field, payload)
            return None

    if str(payload["merchant_id"]) != str(expected_merchant_id):
        logger.warning(
            "Tenant isolation mismatch: event merchant_id=%s does not match expected_merchant_id=%s",
            payload.get("merchant_id"),
            expected_merchant_id,
        )
        return None

    return payload


class MerchantConnectionManager:
    """
    Tracks active WebSocket connections per merchant and coordinates Redis Pub/Sub listeners.
    """

    def __init__(self, redis_client_override: Optional[Any] = None):
        self._connections: Dict[uuid.UUID, Set[WebSocket]] = defaultdict(set)
        self._device_connections: Dict[uuid.UUID, WebSocket] = {}
        self._ws_to_device: Dict[WebSocket, uuid.UUID] = {}
        self._redis_tasks: Dict[uuid.UUID, asyncio.Task] = {}
        self._lock = asyncio.Lock()
        self._redis_client_override = redis_client_override

    async def _get_redis(self):
        if self._redis_client_override is not None:
            return self._redis_client_override
        return await get_redis_client()

    async def connect(
        self,
        merchant_id: uuid.UUID,
        websocket: WebSocket,
        device_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Register an authenticated, accepted WebSocket connection under a merchant."""
        async with self._lock:
            self._connections[merchant_id].add(websocket)
            if device_id is not None:
                self._device_connections[device_id] = websocket
                self._ws_to_device[websocket] = device_id
            logger.info(
                "Merchant %s client connected (active clients: %d, device: %s)",
                merchant_id,
                len(self._connections[merchant_id]),
                device_id,
            )
            # Start Redis listener task if this is the first client for this merchant
            if merchant_id not in self._redis_tasks or self._redis_tasks[merchant_id].done():
                self._redis_tasks[merchant_id] = asyncio.create_task(
                    self._listen_merchant_channel(merchant_id)
                )

    async def disconnect(self, merchant_id: uuid.UUID, websocket: WebSocket) -> None:
        """Unregister a disconnected WebSocket and stop Redis listener if no clients remain."""
        async with self._lock:
            if websocket in self._ws_to_device:
                dev_id = self._ws_to_device.pop(websocket)
                self._device_connections.pop(dev_id, None)

            if merchant_id in self._connections:
                self._connections[merchant_id].discard(websocket)
                remaining = len(self._connections[merchant_id])
                logger.info("Merchant %s client disconnected (active clients: %d)", merchant_id, remaining)

                if remaining == 0:
                    del self._connections[merchant_id]
                    task = self._redis_tasks.pop(merchant_id, None)
                    if task and not task.done():
                        task.cancel()
                        logger.info("Stopped Redis listener for idle merchant %s", merchant_id)

    async def send_to_device(self, device_id: uuid.UUID, message: Dict[str, Any]) -> bool:
        """
        Send a message directly to a targeted Soundbox device WebSocket.
        Returns True if delivered, False if the device is offline or send failed.
        """
        async with self._lock:
            ws = self._device_connections.get(device_id)

        if ws is None:
            return False

        try:
            await ws.send_json(message)
            return True
        except Exception as exc:
            logger.warning("Failed sending message to device %s: %s", device_id, exc)
            return False

    def is_device_connected(self, device_id: uuid.UUID) -> bool:
        """Check if a specific Soundbox device currently maintains an active connection."""
        return device_id in self._device_connections

    async def broadcast_to_merchant(self, merchant_id: uuid.UUID, message: Dict[str, Any]) -> int:
        """
        Validate and broadcast a message to all active WebSocket clients for a merchant.
        Returns the count of successfully notified clients.
        """
        validated = validate_event_payload(message, expected_merchant_id=merchant_id)
        if validated is None:
            return 0

        # Snapshot current connections
        clients = list(self._connections.get(merchant_id, set()))
        if not clients:
            return 0

        successful_deliveries = 0
        dead_clients = []

        for ws in clients:
            try:
                await ws.send_json(validated)
                successful_deliveries += 1
            except Exception as exc:
                logger.warning("Error sending message to merchant %s client: %s", merchant_id, exc)
                dead_clients.append(ws)

        # Clean up any dead connections
        for dead_ws in dead_clients:
            await self.disconnect(merchant_id, dead_ws)

        return successful_deliveries

    async def _listen_merchant_channel(self, merchant_id: uuid.UUID) -> None:
        """
        Background task: Subscribes to the merchant's Redis event channel and broadcasts
        incoming messages to that merchant's active WebSocket connections.
        """
        channel_name = f"voiceledger:merchant:{merchant_id}:events"
        logger.info("Starting Redis listener for channel '%s'", channel_name)

        try:
            redis_client = await self._get_redis()
            pubsub = redis_client.pubsub()
            await pubsub.subscribe(channel_name)

            try:
                async for message in pubsub.listen():
                    if not message or message.get("type") != "message":
                        continue

                    raw_data = message.get("data")
                    if isinstance(raw_data, bytes):
                        raw_data = raw_data.decode("utf-8")

                    try:
                        parsed_payload = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                    except (json.JSONDecodeError, TypeError) as exc:
                        logger.warning("Ignoring malformed JSON from Redis channel %s: %s", channel_name, exc)
                        continue

                    await self.broadcast_to_merchant(merchant_id, parsed_payload)

            finally:
                try:
                    await pubsub.unsubscribe(channel_name)
                    await pubsub.aclose()
                except Exception:
                    pass

        except asyncio.CancelledError:
            logger.info("Redis listener task cancelled for merchant %s", merchant_id)
        except (RedisError, OSError, Exception) as exc:
            logger.error("Redis error in listener for merchant %s: %s", merchant_id, exc)

    def get_active_client_count(self, merchant_id: uuid.UUID) -> int:
        """Return number of currently active connections for a merchant."""
        return len(self._connections.get(merchant_id, set()))


# Global singleton connection manager
merchant_ws_manager = MerchantConnectionManager()
