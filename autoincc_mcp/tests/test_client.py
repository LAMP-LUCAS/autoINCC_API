from unittest.mock import AsyncMock

import httpx
import pytest

from autoincc_mcp.client import (
    APIClient,
    APIError,
    AuthError,
    ForbiddenError,
    NotFoundError,
    RateLimitError,
)


@pytest.fixture
async def client(monkeypatch):
    instance = APIClient()
    monkeypatch.setattr(instance._client, "request", AsyncMock())
    monkeypatch.setattr("autoincc_mcp.client.asyncio.sleep", AsyncMock())
    yield instance
    await instance.close()


async def test_byok_does_not_persist(client):
    client._client.request.return_value = httpx.Response(200, json={"value": "1.2300"})
    assert await client.get("/api/v1/incc/latest", api_key="fixture-key") == {"value": "1.2300"}
    client._client.request.assert_awaited_with(
        "GET", "/api/v1/incc/latest", params=None, json=None, headers={"X-API-KEY": "fixture-key"}
    )
    await client.get("/api/v1/incc/latest")
    assert client._client.request.call_args.kwargs["headers"] == {}
    assert "X-API-KEY" not in client._client.headers


async def test_post(client):
    client._client.request.return_value = httpx.Response(200, json={})
    assert (
        await client.post(
            "/api/v1/incc/correction", json={"valor_inicial": "1.20"}, api_key="fixture-key"
        )
        == {}
    )
    assert client._client.request.call_args.args[0] == "POST"
    assert client._client.request.call_args.kwargs["json"] == {"valor_inicial": "1.20"}


@pytest.mark.parametrize(
    "status,error",
    [
        (401, AuthError),
        (403, ForbiddenError),
        (404, NotFoundError),
        (402, APIError),
        (422, APIError),
    ],
)
async def test_mapping_no_retry(client, status, error, caplog):
    client._client.request.return_value = httpx.Response(status, text="fixture-key")
    with pytest.raises(error) as exc:
        await client.get("/api/v1/incc/latest", api_key="fixture-key")
    assert "correlation_id=" in str(exc.value)
    assert "fixture-key" not in str(exc.value) + caplog.text
    assert client._client.request.await_count == 1


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
async def test_retry_then_success(client, status):
    client._client.request.side_effect = [
        httpx.Response(status, headers={"Retry-After": "2"}),
        httpx.Response(200, json={}),
    ]
    assert await client.get("/api/v1/incc/latest") == {}
    assert client._client.request.await_count == 2


async def test_exhausted_rate_limit(client):
    client._client.request.return_value = httpx.Response(429, headers={"Retry-After": "2"})
    with pytest.raises(RateLimitError) as exc:
        await client.get("/api/v1/incc/latest")
    assert exc.value.retry_after == 2
    assert client._client.request.await_count == 3


@pytest.mark.parametrize(
    "error", [httpx.ReadTimeout("fixture-key"), httpx.ConnectError("fixture-key")]
)
async def test_transport_failure(client, error):
    client._client.request.side_effect = error
    with pytest.raises(APIError) as exc:
        await client.get("/api/v1/incc/latest")
    assert "fixture-key" not in str(exc.value)
    assert client._client.request.await_count == 3


async def test_invalid_json(client):
    client._client.request.return_value = httpx.Response(200, text="not json")
    with pytest.raises(APIError):
        await client.get("/api/v1/incc/latest")
