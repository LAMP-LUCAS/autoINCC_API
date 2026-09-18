from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import Field, validate_call

from autoincc_mcp.cache import cache_key
from autoincc_mcp.tools.tier_1 import (
    Limit,
    Offset,
    Sigla,
    get_cache,
    get_client,
    normalize_sigla,
    validate_dates,
)


async def _get(path: str, params: dict, api_key: str | None) -> dict | list:
    params = {
        k: v.isoformat() if isinstance(v, date) else v for k, v in params.items() if v is not None
    }
    key = cache_key(path, params, api_key=api_key)
    return await get_cache().get_or_fetch(
        key, lambda: get_client().get(path, params=params or None, api_key=api_key)
    )


@validate_call
async def incc_correction(
    valor_inicial: Annotated[Decimal, Field(gt=0)],
    data_inicio: date,
    data_fim: date,
    sigla: str = "INCC-M",
    api_key: str | None = None,
) -> dict | list:
    validate_dates(data_inicio, data_fim)
    body = {
        "valor_inicial": str(valor_inicial),
        "data_inicio": data_inicio.isoformat(),
        "data_fim": data_fim.isoformat(),
        "sigla": normalize_sigla(sigla.strip()),
    }
    key = cache_key("POST:/api/v1/incc/correction", {"body": body}, api_key=api_key)
    return await get_cache().get_or_fetch(
        key, lambda: get_client().post("/api/v1/incc/correction", json=body, api_key=api_key)
    )


@validate_call
async def incc_overview(api_key: str | None = None) -> dict | list:
    return await _get("/api/v1/incc/overview", {}, api_key)


@validate_call
async def incc_compare(
    data_inicio: date | None = None,
    data_fim: date | None = None,
    skip: Offset = 0,
    limit: Limit = 100,
    api_key: str | None = None,
) -> dict | list:
    validate_dates(data_inicio, data_fim)
    return await _get(
        "/api/v1/incc/compare",
        {"data_inicio": data_inicio, "data_fim": data_fim, "skip": skip, "limit": limit},
        api_key,
    )


@validate_call
async def incc_seasonality(sigla: Sigla = "INCC-M", api_key: str | None = None) -> dict | list:
    return await _get("/api/v1/incc/analytics/seasonality", {"sigla": sigla}, api_key)


@validate_call
async def incc_stats(sigla: Sigla = "INCC-M", api_key: str | None = None) -> dict | list:
    return await _get("/api/v1/incc/analytics/stats", {"sigla": sigla}, api_key)
