"""Request-scoped API-key resolution for AutoINCC MCP tools."""

from __future__ import annotations

from typing import Any, cast

from autoincc_mcp.client import AuthError


def _header_values(headers: Any, name: str) -> list[str]:
    if headers is None:
        return []
    getlist = getattr(headers, "getlist", None)
    if callable(getlist):
        values = cast(list[Any], getlist(name) or [])
        return [str(value).strip() for value in values if str(value).strip()]
    value = headers.get(name)
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _request_from_context(ctx: object | None) -> Any | None:
    if ctx is None:
        return None
    try:
        request_context = getattr(ctx, "request_context")
        return getattr(request_context, "request")
    except (AttributeError, RuntimeError, ValueError):
        return None


def resolve_api_key(ctx: object | None = None, explicit: str | None = None) -> str | None:
    request = _request_from_context(ctx)
    if request is None:
        return explicit
    values = _header_values(getattr(request, "headers", None), "x-api-key")
    if len(values) == 1:
        return values[0]
    raise AuthError("X-API-KEY ausente, duplicado ou inválido para transporte HTTP MCP")
