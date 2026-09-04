"""Unit tests for AnalyticsService domain logic (TDD)."""

from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy.orm import Session

from app.db.models import DimTempo, FatoINCC
from app.db.session import seed_default_dimensions
from app.services.analytics_service import AnalyticsService


from app.services.analytics_service import AnalyticsService



def test_get_market_overview(db_session: Session, multi_month_seeded_data: None) -> None:
    """Verifies consolidated overview calculations, latest rates, and spreads."""
    overview = AnalyticsService.get_market_overview(db_session)
    assert overview is not None
    assert overview.data_referencia == date(2024, 6, 1)

    # Check INCC-M: 0.90%
    assert overview.incc_m is not None
    assert overview.incc_m.variacao_mensal_percentual == Decimal("0.9000")

    # Check INCC-DI: 1.10%
    assert overview.incc_di is not None
    assert overview.incc_di.variacao_mensal_percentual == Decimal("1.1000")

    # Check Spread: 0.90 - 1.10 = -0.20 p.p.
    assert overview.spread_mensal_pontos == Decimal("-0.2000")

    # Check Acceleration: 0.90 - 1.50 (prior month) = -0.60 p.p. -> 'desacelerando'
    assert overview.aceleracao_incc_m is not None
    assert overview.aceleracao_incc_m.delta_mes_anterior_pontos == Decimal("-0.6000")
    assert overview.aceleracao_incc_m.tendencia == "desacelerando"


def test_get_comparison_series(db_session: Session, multi_month_seeded_data: None) -> None:
    """Verifies aligned side-by-side time series comparison with spread and dominant variant."""
    comp = AnalyticsService.get_comparison_series(db_session)
    assert comp.total_periodos == 6
    assert len(comp.items) == 6

    # First month: 0.50% vs 0.40% -> spread +0.10, INCC-M higher
    item0 = comp.items[0]
    assert item0.data_id == date(2024, 1, 1)
    assert item0.incc_m_variacao_percentual == Decimal("0.5000")
    assert item0.incc_di_variacao_percentual == Decimal("0.4000")
    assert item0.spread_variacao_pontos == Decimal("0.1000")
    assert item0.variante_maior_taxa == "INCC-M"

    # Month 4: 0.60% vs 0.60% -> EMPATE
    item3 = comp.items[3]
    assert item3.spread_variacao_pontos == Decimal("0.0000")
    assert item3.variante_maior_taxa == "EMPATE"

    # Last month: 0.90% vs 1.10% -> INCC-DI higher
    item5 = comp.items[5]
    assert item5.spread_variacao_pontos == Decimal("-0.2000")
    assert item5.variante_maior_taxa == "INCC-DI"


def test_get_seasonality_analysis(db_session: Session, multi_month_seeded_data: None) -> None:
    """Verifies monthly calendar seasonality aggregation."""
    season = AnalyticsService.get_seasonality_analysis(db_session, sigla="INCC-M")
    assert season is not None
    assert season.sigla == "INCC-M"
    assert season.total_observacoes == 6
    assert len(season.meses) == 6

    # Month 5 (Maio) was 1.50%
    may = [m for m in season.meses if m.mes == 5][0]
    assert may.nome_mes == "Maio"
    assert may.media_variacao_percentual == Decimal("1.5000")
    assert may.probabilidade_alta_percentual == Decimal("100.00")


def test_get_series_statistics(db_session: Session, multi_month_seeded_data: None) -> None:
    """Verifies statistical indicators, record highs, lows, and annualized volatility."""
    stats = AnalyticsService.get_series_statistics(db_session, sigla="INCC-M")
    assert stats is not None
    assert stats.sigla == "INCC-M"
    assert stats.total_observacoes == 6
    assert stats.data_inicio == date(2024, 1, 1)
    assert stats.data_fim == date(2024, 6, 1)

    # Rates: [0.5, 0.8, 1.2, 0.6, 1.5, 0.9] -> Mean = 0.9167%
    assert stats.media_mensal_percentual == Decimal("0.9167")
    # Highest: 1.50% at 2024-05-01
    assert stats.recorde_alta_percentual == Decimal("1.5000")
    assert stats.recorde_alta_data == date(2024, 5, 1)
    # Lowest: 0.50% at 2024-01-01
    assert stats.recorde_baixa_percentual == Decimal("0.5000")
    assert stats.recorde_baixa_data == date(2024, 1, 1)


def test_get_series_metadata() -> None:
    """Verifies technical series metadata retrieval."""
    meta = AnalyticsService.get_series_metadata()
    assert len(meta.series) == 2
    assert meta.series[0].sigla == "INCC-M"
    assert meta.series[0].codigo_bcb == 192
    assert meta.series[1].sigla == "INCC-DI"
    assert meta.series[1].codigo_bcb == 7456
    assert len(meta.notas_metodologicas) >= 2
