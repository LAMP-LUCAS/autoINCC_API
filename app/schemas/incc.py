"""Pydantic V2 schemas for INCC queries, responses, and correction calculations."""

from datetime import date
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class INCCRecordResponse(BaseModel):
    """Schema representing an individual INCC monthly observation with standardized rates."""

    data_id: date = Field(
        ...,
        description="Data de referência do índice (sempre normalizada para o 1º dia do mês: YYYY-MM-01).",
        examples=["2024-06-01"],
    )
    ano: int = Field(..., description="Ano civil de competência da observação.", examples=[2024])
    mes: int = Field(..., description="Número do mês calendário (1 a 12).", examples=[6])
    nome_mes: str = Field(..., description="Nome do mês em português brasileiro.", examples=["Junho"])
    sigla: str = Field(..., description="Sigla da variante do índice ('INCC-M' ou 'INCC-DI').", examples=["INCC-M"])
    fonte: str = Field(..., description="Órgão ou provedor primário dos dados.", examples=["FGV / BCB SGS"])
    variacao_mensal: Decimal = Field(
        ...,
        description="Taxa mensal unitária/decimal normalizada (ex: 0.006100 equivale a 0,61%).",
        examples=[Decimal("0.006100")],
    )
    variacao_mensal_percentual: Decimal = Field(
        ...,
        description="Taxa percentual de variação mensal (ex: 0.6100 equivale a 0,61%).",
        examples=[Decimal("0.6100")],
    )
    variacao_ytd: Optional[Decimal] = Field(
        None,
        description="Variação acumulada no ano corrente (Year-to-Date) em formato decimal unitário.",
        examples=[Decimal("0.049085")],
    )
    variacao_ytd_percentual: Optional[Decimal] = Field(
        None,
        description="Variação acumulada no ano corrente (YTD) em percentual (%).",
        examples=[Decimal("4.9085")],
    )
    variacao_12m: Optional[Decimal] = Field(
        None,
        description="Variação acumulada móvel dos últimos 12 meses em formato decimal unitário.",
        examples=[Decimal("0.064594")],
    )
    variacao_12m_percentual: Optional[Decimal] = Field(
        None,
        description="Variação acumulada móvel dos últimos 12 meses em percentual (%).",
        examples=[Decimal("6.4594")],
    )
    numero_indice: Decimal = Field(
        ...,
        description="Número-índice contínuo (base 100 móvel encadeada) utilizado para reajuste monetário.",
        examples=[Decimal("118.406632")],
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "data_id": "2024-06-01",
                "ano": 2024,
                "mes": 6,
                "nome_mes": "Junho",
                "sigla": "INCC-M",
                "fonte": "FGV / BCB SGS",
                "variacao_mensal": "0.006100",
                "variacao_mensal_percentual": "0.6100",
                "variacao_ytd": "0.049085",
                "variacao_ytd_percentual": "4.9085",
                "variacao_12m": "0.064594",
                "variacao_12m_percentual": "6.4594",
                "numero_indice": "118.406632",
            }
        },
    )


class INCCHistoryResponse(BaseModel):
    """Schema representing a paginated historical series result."""

    total: int = Field(..., description="Contagem total de observações que atendem aos filtros aplicados.", examples=[36])
    skip: int = Field(..., description="Deslocamento/offset de paginação aplicado.", examples=[0])
    limit: int = Field(..., description="Limite de registros retornados por página.", examples=[100])
    sigla: Optional[str] = Field(None, description="Filtro de variante aplicado ou null se foram retornadas todas.", examples=["INCC-M"])
    items: List[INCCRecordResponse] = Field(..., description="Lista ordenada cronologicamente dos registros de índice.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total": 2,
                "skip": 0,
                "limit": 100,
                "sigla": "INCC-M",
                "items": [
                    {
                        "data_id": "2024-01-01",
                        "ano": 2024,
                        "mes": 1,
                        "nome_mes": "Janeiro",
                        "sigla": "INCC-M",
                        "fonte": "FGV / BCB SGS",
                        "variacao_mensal": "0.005000",
                        "variacao_mensal_percentual": "0.5000",
                        "variacao_ytd": "0.005000",
                        "variacao_ytd_percentual": "0.5000",
                        "variacao_12m": "0.032100",
                        "variacao_12m_percentual": "3.2100",
                        "numero_indice": "100.500000",
                    },
                    {
                        "data_id": "2024-02-01",
                        "ano": 2024,
                        "mes": 2,
                        "nome_mes": "Fevereiro",
                        "sigla": "INCC-M",
                        "fonte": "FGV / BCB SGS",
                        "variacao_mensal": "0.008000",
                        "variacao_mensal_percentual": "0.8000",
                        "variacao_ytd": "0.013040",
                        "variacao_ytd_percentual": "1.3040",
                        "variacao_12m": "0.034500",
                        "variacao_12m_percentual": "3.4500",
                        "numero_indice": "101.304000",
                    },
                ],
            }
        }
    )


class INCCCorrectionRequest(BaseModel):
    """Schema for requesting monetary adjustment/correction using INCC index."""

    valor_inicial: Decimal = Field(
        ...,
        gt=0,
        description="Valor monetário nominal a ser corrigido (deve ser estritamente maior que zero).",
        examples=[Decimal("250000.00")],
    )
    data_inicio: date = Field(
        ...,
        description="Data de referência inicial do contrato/parcela (YYYY-MM-DD). Será normalizada para o 1º dia do mês.",
        examples=["2023-01-01"],
    )
    data_fim: date = Field(
        ...,
        description="Data de referência final/atualização monetária (YYYY-MM-DD). Deve ser igual ou posterior à data_inicio.",
        examples=["2024-01-01"],
    )
    sigla: str = Field(
        default="INCC-M",
        description="Variante do índice a utilizar no encadeamento: 'INCC-M' (padrão de mercado para obras) ou 'INCC-DI'.",
        examples=["INCC-M"],
    )

    @field_validator("sigla")
    @classmethod
    def validate_sigla(cls, v: str) -> str:
        upper = v.strip().upper()
        if upper not in ("INCC-M", "INCC-DI"):
            raise ValueError("Sigla must be either 'INCC-M' or 'INCC-DI'")
        return upper

    @model_validator(mode="after")
    def validate_dates(self) -> "INCCCorrectionRequest":
        if self.data_fim < self.data_inicio:
            raise ValueError("data_fim cannot be prior to data_inicio")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "valor_inicial": "250000.00",
                "data_inicio": "2023-01-01",
                "data_fim": "2024-01-01",
                "sigla": "INCC-M",
            }
        }
    )


class INCCCorrectionResponse(BaseModel):
    """Schema returning monetary correction calculation results."""

    valor_inicial: Decimal = Field(
        ...,
        description="Valor monetário nominal original fornecido na requisição.",
        examples=[Decimal("250000.00")],
    )
    valor_corrigido: Decimal = Field(
        ...,
        description="Valor monetário ajustado pelo encadeamento contínuo da inflação do período.",
        examples=[Decimal("258250.00")],
    )
    fator_correcao: Decimal = Field(
        ...,
        description="Fator multiplicador exato calculado pela razão (indice_final / indice_inicial).",
        examples=[Decimal("1.033000")],
    )
    variacao_acumulada_percentual: Decimal = Field(
        ...,
        description="Variação percentual acumulada entre as duas datas: (Fator - 1) * 100.",
        examples=[Decimal("3.3000")],
    )
    data_inicio_utilizada: date = Field(
        ...,
        description="Data de competência inicial efetivamente utilizada no banco de dados.",
        examples=["2023-01-01"],
    )
    data_fim_utilizada: date = Field(
        ...,
        description="Data de competência final efetivamente utilizada no banco de dados.",
        examples=["2024-01-01"],
    )
    indice_inicial: Decimal = Field(
        ...,
        description="Número-índice contínuo na data de início.",
        examples=[Decimal("100.000000")],
    )
    indice_final: Decimal = Field(
        ...,
        description="Número-índice contínuo na data de fim.",
        examples=[Decimal("103.300000")],
    )
    sigla: str = Field(
        ...,
        description="Sigla da série utilizada no cálculo ('INCC-M' ou 'INCC-DI').",
        examples=["INCC-M"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "valor_inicial": "250000.00",
                "valor_corrigido": "258250.00",
                "fator_correcao": "1.033000",
                "variacao_acumulada_percentual": "3.3000",
                "data_inicio_utilizada": "2023-01-01",
                "data_fim_utilizada": "2024-01-01",
                "indice_inicial": "100.000000",
                "indice_final": "103.300000",
                "sigla": "INCC-M",
            }
        }
    )

