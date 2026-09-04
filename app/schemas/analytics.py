"""Pydantic V2 schemas for analytical overviews, series comparison, seasonality, and stats."""

from datetime import date
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field


class INCCCurrentSnapshot(BaseModel):
    """Snapshot of current index rates and multi-window variations."""

    sigla: str = Field(..., description="Index acronym ('INCC-M' or 'INCC-DI')")
    data_id: date = Field(..., description="Observation reference date")
    variacao_mensal_percentual: Decimal = Field(..., description="Monthly rate in percentage")
    numero_indice: Decimal = Field(..., description="Continuous base 100 index value")
    variacao_ytd_percentual: Optional[Decimal] = Field(None, description="Year-to-date rate in percentage")
    variacao_12m_percentual: Optional[Decimal] = Field(None, description="12-month rolling variation in percentage")
    variacao_24m_percentual: Optional[Decimal] = Field(None, description="24-month rolling variation in percentage")
    variacao_36m_percentual: Optional[Decimal] = Field(None, description="36-month rolling variation in percentage")


class INCCAcceleration(BaseModel):
    """Rate acceleration metrics compared to prior month and same month of previous year."""

    delta_mes_anterior_pontos: Optional[Decimal] = Field(
        None, description="Difference in percentage points compared to prior month"
    )
    delta_ano_anterior_pontos: Optional[Decimal] = Field(
        None, description="Difference in percentage points compared to same month last year"
    )
    tendencia: str = Field(
        ..., description="Trend classification: 'acelerando', 'desacelerando', 'estavel'"
    )


class INCCOverviewResponse(BaseModel):
    """Consolidated market overview for the most recent observation month."""

    data_referencia: date = Field(..., description="Latest consolidated observation date")
    incc_m: Optional[INCCCurrentSnapshot] = Field(None, description="Current INCC-M metrics")
    incc_di: Optional[INCCCurrentSnapshot] = Field(None, description="Current INCC-DI metrics")
    spread_mensal_pontos: Optional[Decimal] = Field(
        None, description="Spread between INCC-M and INCC-DI in percentage points (M - DI)"
    )
    aceleracao_incc_m: Optional[INCCAcceleration] = Field(
        None, description="Monthly momentum and acceleration for INCC-M"
    )


class INCCCompareItem(BaseModel):
    """Side-by-side observation comparison for INCC-M and INCC-DI in a single month."""

    data_id: date = Field(..., description="Reference date (YYYY-MM-01)")
    ano: int = Field(..., description="Year")
    mes: int = Field(..., description="Month number")
    incc_m_variacao_percentual: Optional[Decimal] = Field(None, description="INCC-M monthly rate (%)")
    incc_m_indice: Optional[Decimal] = Field(None, description="INCC-M base 100 index")
    incc_di_variacao_percentual: Optional[Decimal] = Field(None, description="INCC-DI monthly rate (%)")
    incc_di_indice: Optional[Decimal] = Field(None, description="INCC-DI base 100 index")
    spread_variacao_pontos: Optional[Decimal] = Field(
        None, description="Spread in percentage points (INCC-M - INCC-DI)"
    )
    variante_maior_taxa: Optional[str] = Field(
        None, description="Which variant had higher inflation: 'INCC-M', 'INCC-DI', or 'EMPATE'"
    )


class INCCCompareResponse(BaseModel):
    """Unified historical time-series comparing variants side-by-side."""

    total_periodos: int = Field(..., description="Total periods matching filter")
    data_inicio: Optional[date] = Field(None, description="Start date filter applied")
    data_fim: Optional[date] = Field(None, description="End date filter applied")
    items: List[INCCCompareItem] = Field(..., description="Chronological list of side-by-side observations")


class INCCMonthSeasonality(BaseModel):
    """Statistical seasonality indicators for an individual calendar month."""

    mes: int = Field(..., description="Month number (1-12)")
    nome_mes: str = Field(..., description="Month name in Portuguese")
    total_anos: int = Field(..., description="Count of historical years sampled")
    media_variacao_percentual: Decimal = Field(..., description="Historical average rate for this month (%)")
    mediana_variacao_percentual: Decimal = Field(..., description="Historical median rate for this month (%)")
    desvio_padrao_pontos: Decimal = Field(..., description="Standard deviation in percentage points")
    minima_variacao_percentual: Decimal = Field(..., description="Lowest rate recorded in this calendar month (%)")
    maxima_variacao_percentual: Decimal = Field(..., description="Highest rate recorded in this calendar month (%)")
    probabilidade_alta_percentual: Decimal = Field(
        ..., description="Historical frequency of positive monthly inflation (%)"
    )


class INCCSeasonalityResponse(BaseModel):
    """Complete 12-month seasonality matrix over full historical series."""

    sigla: str = Field(..., description="Analyzed index acronym")
    periodo_historico: str = Field(..., description="Sampling interval description (e.g. '1994 a 2026')")
    total_observacoes: int = Field(..., description="Total observation count")
    meses: List[INCCMonthSeasonality] = Field(..., description="Seasonality statistics for January to December")


class INCCStatsResponse(BaseModel):
    """Statistical summary metrics for a given series."""

    sigla: str = Field(..., description="Index acronym")
    total_observacoes: int = Field(..., description="Total historical monthly observations")
    data_inicio: date = Field(..., description="First observation date in series")
    data_fim: date = Field(..., description="Latest observation date in series")
    media_mensal_percentual: Decimal = Field(..., description="Overall arithmetic mean of monthly rates (%)")
    mediana_mensal_percentual: Decimal = Field(..., description="Median monthly rate (%)")
    desvio_padrao_mensal_pontos: Decimal = Field(..., description="Sample standard deviation in percentage points")
    volatilidade_anualizada_percentual: Decimal = Field(
        ..., description="Annualized volatility (sigma * sqrt(12)) in percentage"
    )
    recorde_alta_percentual: Decimal = Field(..., description="Highest single monthly variation in series (%)")
    recorde_alta_data: date = Field(..., description="Date of highest recorded variation")
    recorde_baixa_percentual: Decimal = Field(..., description="Lowest single monthly variation in series (%)")
    recorde_baixa_data: date = Field(..., description="Date of lowest recorded variation")


class INCCSeriesMetadataItem(BaseModel):
    """Metadata specification for an individual index variant."""

    sigla: str = Field(..., description="Index acronym")
    codigo_bcb: int = Field(..., description="Central Bank SGS numerical series code")
    nome_oficial: str = Field(..., description="Official series designation")
    fonte_primaria: str = Field(..., description="Primary data publisher")
    instituto_responsavel: str = Field(..., description="Research institute responsible for methodology")
    janela_coleta: str = Field(..., description="Monthly survey calendar collection window")
    periodicidade: str = Field(..., description="Publication frequency")
    inicio_serie: str = Field(..., description="Start year of historical coverage")
    metodologia: str = Field(..., description="Methodology overview and weighting notes")


class INCCMetadataResponse(BaseModel):
    """Complete governance and technical metadata for AutoINCC platform."""

    series: List[INCCSeriesMetadataItem] = Field(..., description="Catalog of available index variants")
    notas_metodologicas: List[str] = Field(..., description="Governance and structural revision notes")
