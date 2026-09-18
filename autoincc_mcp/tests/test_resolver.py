import pytest

from autoincc_mcp.resolver import resolve_resource


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/incc/latest",
        "/api/v1/incc/history",
        "/api/v1/incc/analytics/stats",
        "/api/v1/incc/correction",
        "/api/v1/incc/metadata",
    ],
)
def test_known_resource(path):
    assert resolve_resource(path) != "recurso"


def test_unknown_resource():
    assert resolve_resource("/unknown") == "recurso"
