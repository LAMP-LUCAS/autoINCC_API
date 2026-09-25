from types import SimpleNamespace

import pytest
from mcp.server.fastmcp import Context

from autoincc_mcp.auth import resolve_api_key
from autoincc_mcp.client import AuthError


def context_for(key=None):
    headers = {} if key is None else {"x-api-key": key}
    request = SimpleNamespace(headers=headers)
    return Context(request_context=SimpleNamespace(request=request))


def test_http_requires_one_key():
    with pytest.raises(AuthError):
        resolve_api_key(context_for())
    with pytest.raises(AuthError):
        resolve_api_key(context_for(["a", "b"]))
    assert resolve_api_key(context_for("caller"), "ignored") == "caller"


def test_stdio_keeps_explicit_compatibility_key():
    assert resolve_api_key(None, "local-key") == "local-key"
