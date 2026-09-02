import logging
from typing import Optional
import redis.asyncio as aioredis
from redis.exceptions import RedisError
from backend.app.config import settings

logger = logging.getLogger("voiceledger.redis")

_redis_client: Optional[aioredis.Redis] = None


async def get_redis_client() -> aioredis.Redis:
    """Obtain or initialize the global async Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_timeout=3.0,
            socket_connect_timeout=3.0,
        )
    return _redis_client


async def close_redis_connection() -> None:
    """Close the global Redis connection gracefully."""
    global _redis_client
    if _redis_client is not None:
        try:
            await _redis_client.aclose()
            logger.info("Redis connection closed")
        except Exception as e:
            logger.warning("Error closing Redis connection: %s", e)
        finally:
            _redis_client = None


async def check_redis_health(client_override: Optional[aioredis.Redis] = None) -> bool:
    """Ping Redis to determine connectivity for health checks."""
    client = client_override
    try:
        if client is None:
            client = await get_redis_client()
        pong = await client.ping()
        return bool(pong)
    except (RedisError, OSError, Exception) as e:
        logger.warning("Redis health check probe failed: %s", e)
        return False
