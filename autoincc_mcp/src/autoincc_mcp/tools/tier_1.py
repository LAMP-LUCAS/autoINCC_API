from datetime import date
from typing import Annotated

from pydantic import AfterValidator, Field, validate_call

from autoincc_mcp.cache import CacheManager, cache_key
from autoincc_mcp.client import APIClient

_client: APIClient | None = None
_cache: CacheManager | None = None


def get_client() -> APIClient:
    global _client
    if _client is None:
        _client = APIClient()
    return _client


def get_cache() -> CacheManager:
    global _cache
    if _cache is None:
        _cache = CacheManager()
    return _cache


async def close_resources() -> None:
    global _client, _cache
    try:
        if _client is not None:
            await _client.close()
    finally:
        _client = None
        if _cache is not None:
            await _cache.close()
        _cache = None


def normalize_sigla(value: str) -> str:
    value = value.upper()
    if value not in ("INCC-M", "INCC-DI"):
        raise ValueError("Sigla must be INCC-M or INCC-DI")
    return value


Sigla = Annotated[str, AfterValidator(normalize_sigla)]
Offset = Annotated[int, Field(ge=0)]
Limit = Annotated[int, Field(ge=1, le=1000)]


def validate_dates(data_inicio: date | None, data_fim: date | None) -> None:
    if data_inicio and data_fim and data_fim < data_inicio:
        raise ValueError("data_fim cannot be prior to data_inicio")


async def _get(path: str, params: dict, api_key: str | None) -> dict | list:
    params = {
        k: v.isoformat() if isinstance(v, date) else v for k, v in params.items() if v is not None
    }
    key = cache_key(path, params, api_key=api_key)
    return await get_cache().get_or_fetch(
        key, lambda: get_client().get(path, params=params or None, api_key=api_key)
    )


@validate_call
async def incc_latest(sigla: Sigla = "INCC-M", api_key: str | None = None) -> dict | list:
    return await _get("/api/v1/incc/latest", {"sigla": sigla}, api_key)


@validate_call
async def incc_history(
    data_inicio: date,
    data_fim: date,
    sigla: str | None = "INCC-M",
    skip: Offset = 0,
    limit: Limit = 100,
    api_key: str | None = None,
) -> dict | list:
    validate_dates(data_inicio, data_fim)
    return await _get(
        "/api/v1/incc/history",
        {
            "data_inicio": data_inicio,
            "data_fim": data_fim,
            "sigla": sigla if sigla is not None else "",
            "skip": skip,
            "limit": limit,
        },
        api_key,
    )


@validate_call
async def incc_metadata(api_key: str | None = None) -> dict | list:
    return await _get("/api/v1/incc/metadata", {}, api_key)
