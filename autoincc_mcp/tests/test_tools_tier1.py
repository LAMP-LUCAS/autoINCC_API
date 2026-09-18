from unittest.mock import AsyncMock

import pytest

from autoincc_mcp.tools import tier_1

CASES = [
    ("incc_latest", {}, "/api/v1/incc/latest", {"sigla": "INCC-M"}),
    (
        "incc_history",
        {"data_inicio": "2024-01-01", "data_fim": "2024-12-01"},
        "/api/v1/incc/history",
        {
            "data_inicio": "2024-01-01",
            "data_fim": "2024-12-01",
            "sigla": "INCC-M",
            "skip": 0,
            "limit": 100,
        },
    ),
    ("incc_metadata", {}, "/api/v1/incc/metadata", {}),
]


@pytest.mark.parametrize("name,arguments,path,params", CASES)
async def test_route_and_auth_partition(monkeypatch, name, arguments, path, params):
    client = AsyncMock()
    client.get.return_value = {"value": "1.2300", "source": "FGV"}
    cache = AsyncMock()

    async def fetch(key, fetch_fn, **kwargs):
        assert key.startswith("autoincc:")
        assert "fixture-key" not in key
        return await fetch_fn()

    cache.get_or_fetch.side_effect = fetch
    monkeypatch.setattr(tier_1, "get_client", lambda: client)
    monkeypatch.setattr(tier_1, "get_cache", lambda: cache)
    tool = getattr(tier_1, name)
    assert await tool(**arguments, api_key="fixture-key") == client.get.return_value
    client.get.assert_awaited_once_with(path, params=params or None, api_key="fixture-key")
    first_key = cache.get_or_fetch.call_args.args[0]
    await tool(**arguments, api_key="another-key")
    assert cache.get_or_fetch.call_args.args[0] != first_key


@pytest.mark.parametrize(
    "arguments",
    [
        {"data_inicio": "2025-01-01", "data_fim": "2024-01-01"},
        {"data_inicio": "bad", "data_fim": "2024-01-01"},
        {"data_inicio": "2024-01-01", "data_fim": "2024-12-01", "limit": 1001},
        {"data_inicio": "2024-01-01", "data_fim": "2024-12-01", "skip": -1},
    ],
)
async def test_history_invalid(arguments):
    with pytest.raises(ValueError):
        await tier_1.incc_history(**arguments)
