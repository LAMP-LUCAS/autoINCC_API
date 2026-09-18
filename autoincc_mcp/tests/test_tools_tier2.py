from unittest.mock import AsyncMock

import pytest

from autoincc_mcp.tools import tier_2


@pytest.mark.parametrize(
    "name,arguments,path,params",
    [
        ("incc_overview", {}, "/api/v1/incc/overview", None),
        ("incc_compare", {}, "/api/v1/incc/compare", {"skip": 0, "limit": 100}),
        (
            "incc_seasonality",
            {"sigla": "incc-di"},
            "/api/v1/incc/analytics/seasonality",
            {"sigla": "INCC-DI"},
        ),
        ("incc_stats", {}, "/api/v1/incc/analytics/stats", {"sigla": "INCC-M"}),
    ],
)
async def test_analytics(monkeypatch, name, arguments, path, params):
    client = AsyncMock()
    client.get.return_value = {"value": "1.2300"}
    monkeypatch.setattr(tier_2, "get_client", lambda: client)
    result = await getattr(tier_2, name)(**arguments, api_key="fixture-key")
    assert result == client.get.return_value
    client.get.assert_awaited_once_with(path, params=params, api_key="fixture-key")


@pytest.mark.parametrize(
    "name,args",
    [
        ("incc_overview", {}),
        ("incc_compare", {"data_inicio": "2024-01-01", "data_fim": "2024-12-01"}),
        ("incc_seasonality", {}),
        ("incc_stats", {}),
        (
            "incc_correction",
            {"valor_inicial": "10.00", "data_inicio": "2024-01-01", "data_fim": "2024-12-01"},
        ),
    ],
)
async def test_analytics_cache_partition(monkeypatch, name, args):
    client = AsyncMock()
    cache = AsyncMock()

    async def fetch(key, fetch_fn, **kwargs):
        return await fetch_fn()

    cache.get_or_fetch.side_effect = fetch
    monkeypatch.setattr(tier_2, "get_client", lambda: client)
    monkeypatch.setattr(tier_2, "get_cache", lambda: cache)
    await getattr(tier_2, name)(**args, api_key="fixture-key")
    first = cache.get_or_fetch.call_args.args[0]
    await getattr(tier_2, name)(**args, api_key="other-key")
    assert first != cache.get_or_fetch.call_args.args[0]
    assert "fixture-key" not in first


async def test_correction_posts_decimal_body(monkeypatch):
    client = AsyncMock()
    client.post.return_value = {"valor_corrigido": "258250.00"}
    monkeypatch.setattr(tier_2, "get_client", lambda: client)
    payload = {
        "valor_inicial": "250000.00",
        "data_inicio": "2023-01-01",
        "data_fim": "2024-01-01",
        "sigla": "INCC-M",
    }
    assert (
        await tier_2.incc_correction(**payload, api_key="fixture-key") == client.post.return_value
    )
    client.post.assert_awaited_once_with(
        "/api/v1/incc/correction", json=payload, api_key="fixture-key"
    )


@pytest.mark.parametrize(
    "update", [{"valor_inicial": "0"}, {"sigla": "OTHER"}, {"data_fim": "2022-01-01"}]
)
async def test_correction_invalid(update):
    args = {"valor_inicial": "1.00", "data_inicio": "2023-01-01", "data_fim": "2024-01-01"}
    with pytest.raises(ValueError):
        await tier_2.incc_correction(**(args | update))
