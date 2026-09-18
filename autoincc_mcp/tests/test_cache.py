import hashlib
from unittest.mock import AsyncMock

import pytest

from autoincc_mcp.cache import CacheManager, cache_key
from autoincc_mcp.client import ForbiddenError


def test_keys():
    first = cache_key("latest", {"a": 1, "b": None}, api_key="fixture-key")
    assert first.startswith("autoincc:")
    assert hashlib.sha256(b"fixture-key").hexdigest()[:32] in first
    assert "fixture-key" not in first
    assert first == cache_key("latest", {"a": 1}, api_key="fixture-key")
    assert first != cache_key("latest", {"a": 1}, api_key="other-key")
    assert first != cache_key("latest", {"a": 1})
    assert cache_key("x", {"a": "b:c=d"}) != cache_key("x", {"a": "b", "c": "d"})
    assert cache_key("x", {"a": {"b": 1, "c": 2}}) == cache_key("x", {"a": {"c": 2, "b": 1}})


@pytest.fixture
async def cache():
    redis = AsyncMock()
    redis.get.return_value = None
    manager = CacheManager(redis_client=redis)
    yield manager
    await manager.close()


async def test_cache_hit_requires_authorization(cache):
    cache._redis.get.return_value = '{"value": "1.2300"}'
    authorize = AsyncMock(return_value=True)
    fetch = AsyncMock()
    assert await cache.get_or_fetch("key", fetch, authorize=authorize) == {"value": "1.2300"}
    authorize.assert_awaited_once()
    fetch.assert_not_awaited()


async def test_no_admission_bypasses_cache(cache):
    cache._redis.get.return_value = '{"cached": true}'
    fetch = AsyncMock(return_value={"fresh": True})
    assert await cache.get_or_fetch("key", fetch) == {"fresh": True}
    cache._redis.get.assert_not_awaited()
    cache._redis.setex.assert_not_awaited()


async def test_revoked_caller_never_reads_warm_cache(cache):
    authorize = AsyncMock(return_value=False)
    with pytest.raises(ForbiddenError):
        await cache.get_or_fetch("key", AsyncMock(), authorize=authorize)
    cache._redis.get.assert_not_awaited()


async def test_unavailable_authorization_never_reads(cache):
    with pytest.raises(ForbiddenError):
        await cache.get_or_fetch(
            "key", AsyncMock(), authorize=AsyncMock(side_effect=RuntimeError())
        )
    cache._redis.get.assert_not_awaited()


async def test_miss_ttl(cache):
    fetch = AsyncMock(return_value=[])
    assert (
        await cache.get_or_fetch("key", fetch, ttl=60, authorize=AsyncMock(return_value=True)) == []
    )
    cache._redis.setex.assert_awaited_once_with("key", 60, "[]")


async def test_redis_failure_falls_back(cache, caplog):
    cache._redis.get.side_effect = RuntimeError("fixture-key")
    cache._redis.setex.side_effect = RuntimeError("fixture-key")
    assert (
        await cache.get_or_fetch(
            "key", AsyncMock(return_value={}), authorize=AsyncMock(return_value=True)
        )
        == {}
    )
    assert "fixture-key" not in caplog.text


async def test_fetch_errors_not_cached(cache):
    with pytest.raises(ForbiddenError):
        await cache.get_or_fetch(
            "key", AsyncMock(side_effect=ForbiddenError()), authorize=AsyncMock(return_value=True)
        )
    cache._redis.setex.assert_not_awaited()


async def test_corrupt_cache_and_invalidate(cache):
    cache._redis.get.return_value = "bad json"
    assert await cache.get("key") is None
    await cache.invalidate("key")
    cache._redis.delete.assert_awaited_once_with("key")
