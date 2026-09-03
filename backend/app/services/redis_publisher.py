"""
VoiceLedger Redis Event Publisher.

Responsible for publishing sanitized OutboxEvent payloads to the Redis event bus
for downstream real-time consumption (WebSocket gateways, device dispatchers).

Invariants:
1. Decoupled: Zero dependency on payment gateways (Razorpay) or financial state logic.
2. Sanitized Payloads Only: Publishes already-verified, sanitized JSON payloads.
3. Resilience: Captures network and Redis errors safely, returning boolean success/failure
   so the outbox worker can schedule deterministic retries.
"""
import json
import logging
from typing import Optional, Dict, Any
import redis.asyncio as aioredis
from redis.exceptions import RedisError

from backend.app.core.redis import get_redis_client

logger = logging.getLogger("voiceledger.outbox.publisher")

GLOBAL_EVENTS_CHANNEL = "voiceledger:events"


class RedisEventPublisher:
    """
    Publisher abstraction for broadcasting outbox events over Redis.
    """

    def __init__(self, redis_client: Optional[aioredis.Redis] = None):
        self._redis_client = redis_client

    async def _get_client(self) -> aioredis.Redis:
        if self._redis_client is not None:
            return self._redis_client
        return await get_redis_client()

    async def publish_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
    ) -> bool:
        """
        Publish an outbox event payload to the global events channel and the
        merchant-scoped channel.

        Returns:
            bool: True if publication succeeded, False if a Redis network or
                  server error occurred.
        """
        try:
            client = await self._get_client()
            message_str = json.dumps(payload, default=str)

            # 1. Publish to global event bus
            await client.publish(GLOBAL_EVENTS_CHANNEL, message_str)

            # 2. Publish to merchant-scoped channel if merchant_id is present
            merchant_id = payload.get("merchant_id")
            if merchant_id:
                merchant_channel = f"voiceledger:merchant:{merchant_id}:events"
                await client.publish(merchant_channel, message_str)

            logger.info(
                "Published outbox event type='%s' aggregate_id=%s to Redis channels [%s, merchant=%s]",
                event_type,
                payload.get("payment_id"),
                GLOBAL_EVENTS_CHANNEL,
                merchant_id,
            )
            return True

        except (RedisError, ConnectionError, OSError, Exception) as exc:
            logger.warning(
                "Failed to publish event type='%s' aggregate_id=%s to Redis: %s",
                event_type,
                payload.get("payment_id"),
                exc,
            )
            return False


# Global default publisher instance
redis_event_publisher = RedisEventPublisher()
