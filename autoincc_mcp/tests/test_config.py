import pytest
from pydantic import ValidationError

from autoincc_mcp.config import DEFAULT_GATEWAY_BASE_URL, Settings, get_config


def test_defaults(monkeypatch):
    monkeypatch.delenv("AUTOINCC_BASE_URL")
    config = Settings()
    assert config.base_url == DEFAULT_GATEWAY_BASE_URL
    assert config.cache_url is None
    assert config.cache_ttl == 300
    assert config.timeout == 30
    assert config.retries == 3
    assert config.mcp_port == 8080
    assert config.mcp_transport == "streamable-http"
    assert "api_key" not in Settings.model_fields
    assert Settings.model_config.get("env_file") is None


def test_environment(monkeypatch):
    monkeypatch.setenv("AUTOINCC_MCP_PORT", "9082")
    monkeypatch.setenv("AUTOINCC_CACHE_URL", "redis://cache:6379/3")
    monkeypatch.setenv("AUTOINCC_CACHE_TTL", "60")
    assert get_config().mcp_port == 9082
    assert get_config().cache_url == "redis://cache:6379/3"
    assert get_config().cache_ttl == 60
    assert get_config() is get_config()


@pytest.mark.parametrize(
    "field,value", [("retries", 0), ("timeout", 0), ("cache_ttl", 0), ("mcp_port", 65536)]
)
def test_invalid_settings(field, value):
    with pytest.raises(ValidationError):
        Settings(**{field: value})
