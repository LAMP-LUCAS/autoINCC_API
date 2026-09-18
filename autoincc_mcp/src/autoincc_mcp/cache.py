import hashlib
import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

import redis.asyncio as aioredis

from autoincc_mcp.client import ForbiddenError
from autoincc_mcp.config import get_config

logger = logging.getLogger(__name__)
_MAX_RECONNECT_BACKOFF = 60.0


def cache_key(prefix: str, params: dict | None = None, api_key: str | None = None) -> str:
    fingerprint = (
        hashlib.sha256(api_key.encode()).hexdigest()[:32] if api_key is not None else "anonymous"
    )
    canonical = json.dumps(
        {k: v for k, v in (params or {}).items() if v is not None},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    return f"autoincc:{prefix}:k={fingerprint}:{digest}"


class CacheManager:
    def __init__(self, redis_client: Any = None):
        config = get_config()
        self._default_ttl = config.cache_ttl
        self._redis = redis_client
        self._reconnect_backoff = 1.0
        self._last_reconnect_attempt = 0.0
        self._healthy = redis_client is not None
        if self._redis is None:
            self._connect_redis()

    def _connect_redis(self) -> None:
        url = get_config().cache_url
        if not url:
            return
        try:
            self._redis = aioredis.from_url(
                url, decode_responses=True, socket_connect_timeout=1, socket_timeout=1
            )
        except Exception:
            logger.warning("Redis unavailable; cache disabled")
            self._redis = None

    def attempt_reconnect(self) -> None:
        if self._redis is not None:
            return
        now = time.monotonic()
        if now - self._last_reconnect_attempt < self._reconnect_backoff:
            return
        self._last_reconnect_attempt = now
        self._connect_redis()
        self._reconnect_backoff = (
            1.0
            if self._redis is not None
            else min(self._reconnect_backoff * 2, _MAX_RECONNECT_BACKOFF)
        )

    def is_healthy(self) -> bool:
        return self._healthy

    def get_status(self) -> dict:
        return {"connected": self._healthy, "reconnect_backoff": self._reconnect_backoff}

    async def get(self, key: str) -> Any | None:
        if self._redis is None:
            return None
        try:
            value = await self._redis.get(key)
            self._healthy = True
            return json.loads(value) if value is not None else None
        except Exception:
            self._healthy = False
            logger.warning("Cache get failed")
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.setex(
                key, ttl if ttl is not None else self._default_ttl, json.dumps(value)
            )
            self._healthy = True
        except Exception:
            self._healthy = False
            logger.warning("Cache set failed")

    async def invalidate(self, key: str) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.delete(key)
        except Exception:
            self._healthy = False
            logger.warning("Cache invalidation failed")

    async def get_or_fetch(
        self,
        key: str,
        fetch_fn: Callable[[], Awaitable[Any]],
        ttl: int | None = None,
        *,
        authorize: Callable[[], Awaitable[bool]] | None = None,
    ) -> Any:
        if authorize is None:
            return await fetch_fn()
        try:
            allowed = await authorize()
        except Exception:
            raise ForbiddenError("Cache admission unavailable") from None
        if allowed is not True:
            raise ForbiddenError("Cache admission denied")
        if self._redis is None:
            self.attempt_reconnect()
        cached = await self.get(key)
        if cached is not None:
            return cached
        data = await fetch_fn()
        await self.set(key, data, ttl=ttl)
        return data

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
        self._healthy = False
