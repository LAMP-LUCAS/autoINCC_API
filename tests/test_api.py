"""Integration and endpoint tests for AutoINCC FastAPI routes."""

from datetime import date
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings


def test_root_endpoint(client: TestClient) -> None:
    """Verifies service info returned by root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == settings.APP_NAME
    assert data["status"] == "online"


def test_health_endpoint(client: TestClient) -> None:
    """Verifies health check probe."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_health_canonical_contract(client: TestClient) -> None:
    """Contrato canônico do gateway: `GET /api/v1/incc/health`.

    Regressão detectada pelo canary: o alias foi registrado como
    `f"{settings.API_V1_STR}/health"`, mas `API_V1_STR` é só `/api/v1` — o
    segmento `/incc` vem do prefixo de `app.api.v1.incc.router`. O path
    canônico respondia 404 enquanto `/api/v1/health` (fora do contrato)
    respondia 200.
    """
    response = client.get("/api/v1/incc/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_get_latest_incc_not_found(client: TestClient) -> None:
    """Verifies 404 response when no data has been populated."""
    response = client.get("/api/v1/incc/latest?sigla=INCC-DI")
    assert response.status_code == 404
    assert "No data found for index 'INCC-DI'" in response.json()["detail"]


def test_get_latest_incc_success(client: TestClient, seeded_incc_data: None) -> None:
    """Verifies retrieval of most recent index observation."""
    response = client.get("/api/v1/incc/latest?sigla=INCC-M")
    assert response.status_code == 200
    data = response.json()
    assert data["data_id"] == "2024-04-01"
    assert data["ano"] == 2024
    assert data["mes"] == 4
    assert data["nome_mes"] == "Abril"
    assert data["sigla"] == "INCC-M"
    assert float(data["variacao_mensal_percentual"]) == 0.50
    assert float(data["numero_indice"]) == 101.407115


def test_get_incc_history_success(client: TestClient, seeded_incc_data: None) -> None:
    """Verifies historical series query with date interval and pagination."""
    response = client.get(
        "/api/v1/incc/history",
        params={
            "data_inicio": "2024-01-01",
            "data_fim": "2024-03-01",
            "sigla": "INCC-M",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3
    assert data["items"][0]["data_id"] == "2024-01-01"
    assert data["items"][2]["data_id"] == "2024-03-01"


def test_get_incc_history_pagination(client: TestClient, seeded_incc_data: None) -> None:
    """Verifies pagination limits and offsets."""
    response = client.get(
        "/api/v1/incc/history",
        params={
            "data_inicio": "2024-01-01",
            "data_fim": "2024-04-01",
            "skip": 1,
            "limit": 2,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 4
    assert len(data["items"]) == 2
    assert data["items"][0]["data_id"] == "2024-02-01"


def test_get_incc_history_invalid_dates(client: TestClient) -> None:
    """Verifies error handling when data_fim is prior to data_inicio."""
    response = client.get(
        "/api/v1/incc/history",
        params={
            "data_inicio": "2024-04-01",
            "data_fim": "2024-01-01",
        },
    )
    assert response.status_code == 422


def test_calculate_incc_correction_endpoint(client: TestClient, seeded_incc_data: None) -> None:
    """Verifies monetary adjustment calculation endpoint."""
    payload = {
        "valor_inicial": 100000.00,
        "data_inicio": "2024-01-01",
        "data_fim": "2024-04-01",
        "sigla": "INCC-M",
    }
    response = client.post("/api/v1/incc/correction", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["valor_inicial"] == "100000.00"
    assert data["indice_inicial"] == "100.300000"
    assert data["indice_final"] == "101.407115"

    # Fator = 101.407115 / 100.300000 ~ 1.011038
    assert float(data["fator_correcao"]) == pytest.approx(1.011038, 1e-4)
    # Valor corrigido ~ 101103.80
    assert float(data["valor_corrigido"]) == pytest.approx(101103.80, 0.1)
    # Variação acumulada ~ 1.1038%
    assert float(data["variacao_acumulada_percentual"]) == pytest.approx(1.1038, 1e-2)


def test_trigger_etl_unauthorized(client: TestClient) -> None:
    """Verifies that missing or invalid API key header results in 403 Forbidden."""
    # No header
    resp_no_header = client.post("/api/v1/etl/trigger")
    assert resp_no_header.status_code == 403

    # Invalid header
    resp_wrong_header = client.post(
        "/api/v1/etl/trigger",
        headers={"X-API-Key": "wrong_key_123"},
    )
    assert resp_wrong_header.status_code == 403


def test_trigger_etl_authorized(client: TestClient) -> None:
    """Verifies that valid API key accepts the ETL task asynchronously."""
    response = client.post(
        "/api/v1/etl/trigger",
        headers={"X-API-Key": settings.API_KEY},
        json={"series_codes": [192]},
    )
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "accepted"
    assert "task_id" in data
    assert data["series"] == [192]
