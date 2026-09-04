"""Integration tests for AutoINCC analytics, comparison, seasonality, and metadata endpoints."""

from decimal import Decimal
import pytest
from fastapi.testclient import TestClient


def test_get_overview_not_found(client: TestClient) -> None:
    """Verifies 404 response when database has no records to generate overview."""
    response = client.get("/api/v1/incc/overview")
    assert response.status_code == 404
    assert "No INCC observations found" in response.json()["detail"]


def test_get_overview_success(client: TestClient, multi_month_seeded_data: None) -> None:
    """Verifies /incc/overview returns complete snapshot with spread and acceleration."""
    response = client.get("/api/v1/incc/overview")
    assert response.status_code == 200
    data = response.json()

    assert data["data_referencia"] == "2024-06-01"
    assert data["incc_m"] is not None
    assert data["incc_m"]["sigla"] == "INCC-M"
    assert float(data["incc_m"]["variacao_mensal_percentual"]) == 0.90
    assert float(data["incc_di"]["variacao_mensal_percentual"]) == 1.10
    assert float(data["spread_mensal_pontos"]) == -0.20

    assert data["aceleracao_incc_m"] is not None
    assert float(data["aceleracao_incc_m"]["delta_mes_anterior_pontos"]) == -0.60
    assert data["aceleracao_incc_m"]["tendencia"] == "desacelerando"


def test_compare_incc_variants_success(client: TestClient, multi_month_seeded_data: None) -> None:
    """Verifies /incc/compare returns aligned series with spread and dominance."""
    response = client.get("/api/v1/incc/compare")
    assert response.status_code == 200
    data = response.json()

    assert data["total_periodos"] == 6
    assert len(data["items"]) == 6

    # Item 0: 2024-01-01 (INCC-M 0.50% vs INCC-DI 0.40%)
    item0 = data["items"][0]
    assert item0["data_id"] == "2024-01-01"
    assert float(item0["incc_m_variacao_percentual"]) == 0.50
    assert float(item0["incc_di_variacao_percentual"]) == 0.40
    assert float(item0["spread_variacao_pontos"]) == 0.10
    assert item0["variante_maior_taxa"] == "INCC-M"

    # Item 3: 2024-04-01 (INCC-M 0.60% vs INCC-DI 0.60%)
    item3 = data["items"][3]
    assert float(item3["spread_variacao_pontos"]) == 0.00
    assert item3["variante_maior_taxa"] == "EMPATE"


def test_compare_incc_variants_invalid_dates(client: TestClient) -> None:
    """Verifies 422 error when data_fim precedes data_inicio."""
    response = client.get(
        "/api/v1/incc/compare",
        params={"data_inicio": "2024-06-01", "data_fim": "2024-01-01"},
    )
    assert response.status_code == 422
    assert "data_fim cannot be prior to data_inicio" in response.json()["detail"]


def test_get_seasonality_analysis_success(client: TestClient, multi_month_seeded_data: None) -> None:
    """Verifies /incc/analytics/seasonality returns monthly statistics."""
    response = client.get("/api/v1/incc/analytics/seasonality?sigla=INCC-M")
    assert response.status_code == 200
    data = response.json()

    assert data["sigla"] == "INCC-M"
    assert data["total_observacoes"] == 6
    assert len(data["meses"]) == 6

    # Month 1 (Janeiro)
    jan = [m for m in data["meses"] if m["mes"] == 1][0]
    assert jan["nome_mes"] == "Janeiro"
    assert float(jan["media_variacao_percentual"]) == 0.50
    assert float(jan["probabilidade_alta_percentual"]) == 100.0


def test_get_seasonality_invalid_sigla(client: TestClient) -> None:
    """Verifies validation error when unknown acronym is requested."""
    response = client.get("/api/v1/incc/analytics/seasonality?sigla=IPCA")
    assert response.status_code == 422


def test_get_series_statistics_success(client: TestClient, multi_month_seeded_data: None) -> None:
    """Verifies /incc/analytics/stats returns aggregated metrics."""
    response = client.get("/api/v1/incc/analytics/stats?sigla=INCC-M")
    assert response.status_code == 200
    data = response.json()

    assert data["sigla"] == "INCC-M"
    assert data["total_observacoes"] == 6
    assert data["data_inicio"] == "2024-01-01"
    assert data["data_fim"] == "2024-06-01"
    assert float(data["media_mensal_percentual"]) == pytest.approx(0.9167, 1e-4)
    assert float(data["recorde_alta_percentual"]) == 1.50
    assert data["recorde_alta_data"] == "2024-05-01"
    assert float(data["recorde_baixa_percentual"]) == 0.50
    assert data["recorde_baixa_data"] == "2024-01-01"


def test_get_series_metadata_endpoint(client: TestClient) -> None:
    """Verifies /incc/metadata returns technical catalog and governance notes."""
    response = client.get("/api/v1/incc/metadata")
    assert response.status_code == 200
    data = response.json()

    assert "series" in data
    assert len(data["series"]) == 2

    # Series 192 (INCC-M)
    incc_m_meta = next(s for s in data["series"] if s["sigla"] == "INCC-M")
    assert incc_m_meta["codigo_bcb"] == 192
    assert "Mercado" in incc_m_meta["nome_oficial"]
    assert "FGV IBRE" in incc_m_meta["instituto_responsavel"]

    # Series 7456 (INCC-DI)
    incc_di_meta = next(s for s in data["series"] if s["sigla"] == "INCC-DI")
    assert incc_di_meta["codigo_bcb"] == 7456
    assert "Disponibilidade Interna" in incc_di_meta["nome_oficial"]

    assert len(data["notas_metodologicas"]) >= 2
