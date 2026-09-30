from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import Field, validate_call
from mcp.server.fastmcp import Context

from autoincc_mcp.auth import resolve_api_key
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


async def _get(path: str, params: dict, ctx: Context | None) -> dict | list:
    api_key = resolve_api_key(ctx)
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
    ctx: Context | None = None,
) -> dict | list:
    api_key = resolve_api_key(ctx)
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
async def incc_overview(ctx: Context | None = None) -> dict | list:
    return await _get("/api/v1/incc/overview", {}, ctx)


@validate_call
async def incc_compare(
    data_inicio: date | None = None,
    data_fim: date | None = None,
    skip: Offset = 0,
    limit: Limit = 100,
    ctx: Context | None = None,
) -> dict | list:
    api_key = resolve_api_key(ctx)
    validate_dates(data_inicio, data_fim)
    return await _get(
        "/api/v1/incc/compare",
        {"data_inicio": data_inicio, "data_fim": data_fim, "skip": skip, "limit": limit},
        ctx,
    )


@validate_call
async def incc_seasonality(sigla: Sigla = "INCC-M", ctx: Context | None = None) -> dict | list:
    return await _get("/api/v1/incc/analytics/seasonality", {"sigla": sigla}, ctx)


@validate_call
async def incc_stats(
    sigla: Sigla = "INCC-M",
    ano_inicio: int | None = None,
    ano_fim: int | None = None,
    ctx: Context | None = None,
) -> dict | list:
    """Estatísticas agregadas da série com janela (§4.4): default de 120 meses;
    `ano_inicio`/`ano_fim` restringem por ano civil e a resposta expõe `janela`."""
    return await _get(
        "/api/v1/incc/analytics/stats",
        {"sigla": sigla, "ano_inicio": ano_inicio, "ano_fim": ano_fim},
        ctx,
    )
