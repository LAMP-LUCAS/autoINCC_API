"""Redis cache client with automatic graceful fallback for high-availability reads.

Provides cached responses for monthly economic indexes, minimizing database I/O.
If Redis is temporarily unavailable, operations gracefully fallback to direct DB access.
"""

import json
from typing import Any, Optional
try:
    import redis
except ImportError:
    redis = None  # type: ignore

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_redis_client: Optional[Any] = None


def get_redis_client() -> Optional[Any]:
    """Returns a singleton Redis client, or None if disabled, unavailable or not installed.

    Returns:
        Optional[Any]: Configured Redis connection or None.
    """
    global _redis_client
    if not settings.CACHE_ENABLED or redis is None:
        return None

    if _redis_client is None:
        try:
            _redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_timeout=2.0,
                socket_connect_timeout=2.0,
            )
            # Fast ping check
            _redis_client.ping()
            logger.info("Connected to Redis cache at %s", settings.REDIS_URL)
        except Exception as exc:
            logger.warning("Redis connection failed (%s). Running with cache disabled.", exc)
            _redis_client = None

    return _redis_client


def get_cache(key: str) -> Optional[Any]:
    """Retrieves cached JSON object from Redis by key.

    Args:
        key (str): Redis cache key.

    Returns:
        Optional[Any]: Parsed JSON data, or None if cache miss or Redis unavailable.
    """
    client = get_redis_client()
    if not client:
        return None

    try:
        val = client.get(key)
        if val:
            logger.debug("Cache HIT for key: %s", key)
            return json.loads(val)
    except Exception as exc:
        logger.warning("Error reading from Redis key '%s': %s", key, exc)
    return None


def set_cache(key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
    """Stores a JSON-serializable value in Redis with a TTL.

    Args:
        key (str): Redis cache key.
        value (Any): JSON-serializable data.
        ttl_seconds (Optional[int]): Time-to-Live in seconds. Defaults to config.

    Returns:
        bool: True if stored successfully, False otherwise.
    """
    client = get_redis_client()
    if not client:
        return False

    ttl = ttl_seconds if ttl_seconds is not None else settings.CACHE_TTL_SECONDS
    try:
        serialized = json.dumps(value, default=str)
        client.set(name=key, value=serialized, ex=ttl)
        logger.debug("Cache SET for key: %s (ttl=%ds)", key, ttl)
        return True
    except Exception as exc:
        logger.warning("Error writing to Redis key '%s': %s", key, exc)
        return False


def invalidate_cache_pattern(pattern: str = "incc:*") -> int:
    """Invalidates all cache keys matching a glob pattern (e.g. 'incc:*').

    Args:
        pattern (str): Glob pattern.

    Returns:
        int: Number of keys deleted.
    """
    client = get_redis_client()
    if not client:
        return 0

    try:
        keys = client.keys(pattern)
        if keys:
            deleted = client.delete(*keys)
            logger.info("Invalidated %d cache keys matching '%s'", deleted, pattern)
            return deleted
    except Exception as exc:
        logger.warning("Error invalidating cache for pattern '%s': %s", pattern, exc)
    return 0
