"""Pydantic V2 schemas for analytical overviews, series comparison, seasonality, and stats."""

from datetime import date
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class INCCCurrentSnapshot(BaseModel):
    """Snapshot of current index rates and multi-window variations."""

    sigla: str = Field(..., description="Sigla da variante do índice ('INCC-M' ou 'INCC-DI').", examples=["INCC-M"])
    data_id: date = Field(..., description="Data de referência da observação mais recente (YYYY-MM-01).", examples=["2024-06-01"])
    variacao_mensal_percentual: Decimal = Field(..., description="Taxa de variação mensal percentual (%).", examples=[Decimal("0.6100")])
    numero_indice: Decimal = Field(..., description="Número-índice contínuo em base 100 móvel encadeada.", examples=[Decimal("118.406632")])
    variacao_ytd_percentual: Optional[Decimal] = Field(None, description="Taxa acumulada no ano corrente (YTD) em percentual (%).", examples=[Decimal("4.9085")])
    variacao_12m_percentual: Optional[Decimal] = Field(None, description="Variação acumulada móvel dos últimos 12 meses em percentual (%).", examples=[Decimal("6.4594")])
    variacao_24m_percentual: Optional[Decimal] = Field(None, description="Variação acumulada móvel dos últimos 24 meses em percentual (%).", examples=[Decimal("14.3580")])
    variacao_36m_percentual: Optional[Decimal] = Field(None, description="Variação acumulada móvel dos últimos 36 meses em percentual (%).", examples=[Decimal("22.1840")])


class INCCAcceleration(BaseModel):
    """Rate acceleration metrics compared to prior month and same month of previous year."""

    delta_mes_anterior_pontos: Optional[Decimal] = Field(
        None,
        description="Diferença em pontos percentuais (p.p.) em relação ao mês imediatamente anterior.",
        examples=[Decimal("-0.1700")],
    )
    delta_ano_anterior_pontos: Optional[Decimal] = Field(
        None,
        description="Diferença em pontos percentuais (p.p.) em relação ao mesmo mês do ano anterior.",
        examples=[Decimal("-0.3000")],
    )
    tendencia: str = Field(
        ...,
        description="Classificação da dinâmica de momento: 'acelerando', 'desacelerando' ou 'estavel'.",
        examples=["desacelerando"],
    )


class INCCOverviewResponse(BaseModel):
    """Consolidated market overview for the most recent observation month."""

    data_referencia: date = Field(..., description="Mês de competência consolidado mais recente disponível.", examples=["2024-06-01"])
    incc_m: Optional[INCCCurrentSnapshot] = Field(None, description="Métricas e acumulados vigentes do INCC-M.")
    incc_di: Optional[INCCCurrentSnapshot] = Field(None, description="Métricas e acumulados vigentes do INCC-DI.")
    spread_mensal_pontos: Optional[Decimal] = Field(
        None,
        description="Diferença pontual de taxas entre variantes em pontos percentuais (INCC-M - INCC-DI).",
        examples=[Decimal("-0.2400")],
    )
    aceleracao_incc_m: Optional[INCCAcceleration] = Field(
        None,
        description="Indicadores de dinâmica, inércia e aceleração inflacionária para a série INCC-M.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data_referencia": "2024-06-01",
                "incc_m": {
                    "sigla": "INCC-M",
                    "data_id": "2024-06-01",
                    "variacao_mensal_percentual": "0.6100",
                    "numero_indice": "118.406632",
                    "variacao_ytd_percentual": "4.9085",
                    "variacao_12m_percentual": "6.4594",
                    "variacao_24m_percentual": "14.3580",
                    "variacao_36m_percentual": "22.1840",
                },
                "incc_di": {
                    "sigla": "INCC-DI",
                    "data_id": "2024-06-01",
                    "variacao_mensal_percentual": "0.8500",
                    "numero_indice": "119.115357",
                    "variacao_ytd_percentual": "5.5900",
                    "variacao_12m_percentual": "6.5542",
                    "variacao_24m_percentual": None,
                    "variacao_36m_percentual": None,
                },
                "spread_mensal_pontos": "-0.2400",
                "aceleracao_incc_m": {
                    "delta_mes_anterior_pontos": "-0.1700",
                    "delta_ano_anterior_pontos": "-0.3000",
                    "tendencia": "desacelerando",
                },
            }
        }
    )


class INCCCompareItem(BaseModel):
    """Side-by-side observation comparison for INCC-M and INCC-DI in a single month."""

    data_id: date = Field(..., description="Data de competência da observação (YYYY-MM-01).", examples=["2024-06-01"])
    ano: int = Field(..., description="Ano da observação.", examples=[2024])
    mes: int = Field(..., description="Número do mês (1-12).", examples=[6])
    incc_m_variacao_percentual: Optional[Decimal] = Field(None, description="Taxa mensal do INCC-M (%).", examples=[Decimal("0.6100")])
    incc_m_indice: Optional[Decimal] = Field(None, description="Número-índice contínuo do INCC-M.", examples=[Decimal("118.406632")])
    incc_di_variacao_percentual: Optional[Decimal] = Field(None, description="Taxa mensal do INCC-DI (%).", examples=[Decimal("0.8500")])
    incc_di_indice: Optional[Decimal] = Field(None, description="Número-índice contínuo do INCC-DI.", examples=[Decimal("119.115357")])
    spread_variacao_pontos: Optional[Decimal] = Field(
        None,
        description="Spread pontual em pontos percentuais (INCC-M - INCC-DI).",
        examples=[Decimal("-0.2400")],
    )
    variante_maior_taxa: Optional[str] = Field(
        None,
        description="Variante com maior pressão de custo no mês: 'INCC-M', 'INCC-DI' ou 'EMPATE'.",
        examples=["INCC-DI"],
    )


class INCCCompareResponse(BaseModel):
    """Unified historical time-series comparing variants side-by-side."""

    total_periodos: int = Field(..., description="Total de períodos mensais incluídos.", examples=[12])
    data_inicio: Optional[date] = Field(None, description="Data inicial do filtro aplicado.", examples=["2024-01-01"])
    data_fim: Optional[date] = Field(None, description="Data final do filtro aplicado.", examples=["2024-12-01"])
    items: List[INCCCompareItem] = Field(..., description="Lista ordenada cronologicamente com observações lado a lado.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_periodos": 1,
                "data_inicio": "2024-06-01",
                "data_fim": "2024-06-01",
                "items": [
                    {
                        "data_id": "2024-06-01",
                        "ano": 2024,
                        "mes": 6,
                        "incc_m_variacao_percentual": "0.6100",
                        "incc_m_indice": "118.406632",
                        "incc_di_variacao_percentual": "0.8500",
                        "incc_di_indice": "119.115357",
                        "spread_variacao_pontos": "-0.2400",
                        "variante_maior_taxa": "INCC-DI",
                    }
                ],
            }
        }
    )


class INCCMonthSeasonality(BaseModel):
    """Statistical seasonality indicators for an individual calendar month."""

    mes: int = Field(..., description="Mês do calendário civil (1 a 12).", examples=[5])
    nome_mes: str = Field(..., description="Nome do mês em português.", examples=["Maio"])
    total_anos: int = Field(..., description="Total de anos civis históricos amostrados.", examples=[83])
    media_variacao_percentual: Decimal = Field(..., description="Média histórica da variação percentual para este mês (%).", examples=[Decimal("4.3471")])
    mediana_variacao_percentual: Decimal = Field(..., description="Mediana histórica da taxa mensal (%).", examples=[Decimal("1.8400")])
    desvio_padrao_pontos: Decimal = Field(..., description="Desvio padrão amostral em pontos percentuais (p.p.).", examples=[Decimal("8.2145")])
    minima_variacao_percentual: Decimal = Field(..., description="Menor variação já registrada neste mês calendário (%).", examples=[Decimal("-2.2200")])
    maxima_variacao_percentual: Decimal = Field(..., description="Maior variação já registrada neste mês calendário (%).", examples=[Decimal("45.6000")])
    probabilidade_alta_percentual: Decimal = Field(
        ...,
        description="Frequência histórica em que o índice fechou positivo neste mês (%).",
        examples=[Decimal("92.77")],
    )


class INCCSeasonalityResponse(BaseModel):
    """Complete 12-month seasonality matrix over full historical series."""

    sigla: str = Field(..., description="Sigla da série analisada ('INCC-M' ou 'INCC-DI').", examples=["INCC-M"])
    periodo_historico: str = Field(..., description="Intervalo cronológico coberto pelo levantamento.", examples=["1944 a 2026"])
    total_observacoes: int = Field(..., description="Quantidade total de meses processados na amostra.", examples=[990])
    meses: List[INCCMonthSeasonality] = Field(..., description="Matriz estatística de Janeiro a Dezembro.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sigla": "INCC-M",
                "periodo_historico": "1944 a 2026",
                "total_observacoes": 990,
                "meses": [
                    {
                        "mes": 5,
                        "nome_mes": "Maio",
                        "total_anos": 83,
                        "media_variacao_percentual": "4.3471",
                        "mediana_variacao_percentual": "1.8400",
                        "desvio_padrao_pontos": "8.2145",
                        "minima_variacao_percentual": "-2.2200",
                        "maxima_variacao_percentual": "45.6000",
                        "probabilidade_alta_percentual": "92.77",
                    }
                ],
            }
        }
    )


class INCCStatsResponse(BaseModel):
    """Statistical summary metrics for a given series."""

    sigla: str = Field(..., description="Sigla da série analisada ('INCC-M' ou 'INCC-DI').", examples=["INCC-M"])
    total_observacoes: int = Field(..., description="Total histórico de observações mensais catalogadas.", examples=[990])
    data_inicio: date = Field(..., description="Data da primeira observação registrada na série.", examples=["1944-02-01"])
    data_fim: date = Field(..., description="Data da última observação registrada na série.", examples=["2026-07-01"])
    media_mensal_percentual: Decimal = Field(..., description="Média aritmética global das taxas mensais (%).", examples=[Decimal("4.0950")])
    mediana_mensal_percentual: Decimal = Field(..., description="Mediana global das taxas mensais (%).", examples=[Decimal("1.0000")])
    desvio_padrao_mensal_pontos: Decimal = Field(..., description="Desvio padrão amostral mensal em pontos percentuais (p.p.).", examples=[Decimal("8.5623")])
    volatilidade_anualizada_percentual: Decimal = Field(
        ...,
        description="Volatilidade anualizada calculada pela métrica padrão sigma * sqrt(12) (%).",
        examples=[Decimal("29.6608")],
    )
    recorde_alta_percentual: Decimal = Field(..., description="Maior taxa de variação mensal registrada em toda a história (%).", examples=[Decimal("78.4100")])
    recorde_alta_data: date = Field(..., description="Data exata em que ocorreu o recorde de alta.", examples=["1990-03-01"])
    recorde_baixa_percentual: Decimal = Field(..., description="Menor taxa de variação mensal registrada em toda a história (%).", examples=[Decimal("-4.4200")])
    recorde_baixa_data: date = Field(..., description="Data exata em que ocorreu o recorde de baixa.", examples=["1945-01-01"])

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sigla": "INCC-M",
                "total_observacoes": 990,
                "data_inicio": "1944-02-01",
                "data_fim": "2026-07-01",
                "media_mensal_percentual": "4.0950",
                "mediana_mensal_percentual": "1.0000",
                "desvio_padrao_mensal_pontos": "8.5623",
                "volatilidade_anualizada_percentual": "29.6608",
                "recorde_alta_percentual": "78.4100",
                "recorde_alta_data": "1990-03-01",
                "recorde_baixa_percentual": "-4.4200",
                "recorde_baixa_data": "1945-01-01",
            }
        }
    )


class INCCSeriesMetadataItem(BaseModel):
    """Metadata specification for an individual index variant."""

    sigla: str = Field(..., description="Sigla oficial da variante do índice.", examples=["INCC-M"])
    codigo_bcb: int = Field(..., description="Código numérico oficial no Sistema Gerenciador de Séries (SGS/BCB).", examples=[192])
    nome_oficial: str = Field(..., description="Denominação completa oficial da série.", examples=["Índice Nacional de Custo da Construção - Mercado"])
    fonte_primaria: str = Field(..., description="Instituição geradora e publicadora primária.", examples=["FGV IBRE / Banco Central do Brasil (SGS)"])
    instituto_responsavel: str = Field(..., description="Instituto técnico responsável pelo cálculo e metodologia.", examples=["Fundação Getulio Vargas (FGV IBRE)"])
    janela_coleta: str = Field(..., description="Janela temporal de pesquisa de preços no mês calendário.", examples=["Do dia 21 do mês anterior ao dia 20 do mês de referência"])
    periodicidade: str = Field(..., description="Periodicidade de apuração e publicação oficial.", examples=["Mensal"])
    inicio_serie: str = Field(..., description="Ano de início da série histórica.", examples=["1944"])
    metodologia: str = Field(..., description="Resumo da metodologia, abrangência geográfica e estrutura de ponderação.")


class INCCMetadataResponse(BaseModel):
    """Complete governance and technical metadata for AutoINCC platform."""

    series: List[INCCSeriesMetadataItem] = Field(..., description="Catálogo técnico de variantes disponíveis na plataforma.")
    notas_metodologicas: List[str] = Field(..., description="Notas de governança, convenções contínuas e marcos de revisão metodológica.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "series": [
                    {
                        "sigla": "INCC-M",
                        "codigo_bcb": 192,
                        "nome_oficial": "Índice Nacional de Custo da Construção - Mercado",
                        "fonte_primaria": "FGV IBRE / Banco Central do Brasil (SGS)",
                        "instituto_responsavel": "Fundação Getulio Vargas (FGV IBRE)",
                        "janela_coleta": "Do dia 21 do mês anterior ao dia 20 do mês de referência",
                        "periodicidade": "Mensal",
                        "inicio_serie": "1944",
                        "metodologia": "Mede a evolução dos custos de construções habitacionais em 7 capitais.",
                    }
                ],
                "notas_metodologicas": [
                    "Revisão Metodológica (Julho/2023): O FGV IBRE introduziu novas estruturas de ponderação.",
                    "Convenção de Encadeamento: Base 100 móvel contínua.",
                ],
            }
        }
    )

