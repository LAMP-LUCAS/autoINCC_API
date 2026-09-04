"""Pydantic V2 schemas for INCC queries, responses, and correction calculations."""

from datetime import date
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class INCCRecordResponse(BaseModel):
    """Schema representing an individual INCC monthly observation."""

    data_id: date = Field(..., description="Reference date (first day of month: YYYY-MM-01)")
    ano: int = Field(..., description="Calendar year")
    mes: int = Field(..., description="Calendar month number (1-12)")
    nome_mes: str = Field(..., description="Portuguese month name")
    sigla: str = Field(..., description="Index acronym (e.g. INCC-M, INCC-DI)")
    fonte: str = Field(..., description="Data provider source")
    variacao_mensal: Decimal = Field(..., description="Normalized monthly rate as decimal (e.g. 0.005400)")
    variacao_mensal_percentual: Decimal = Field(..., description="Monthly variation as percentage (e.g. 0.54%)")
    variacao_ytd: Optional[Decimal] = Field(None, description="Year-to-date rate as decimal")
    variacao_ytd_percentual: Optional[Decimal] = Field(None, description="Year-to-date variation as percentage")
    variacao_12m: Optional[Decimal] = Field(None, description="12-month rolling rate as decimal")
    variacao_12m_percentual: Optional[Decimal] = Field(None, description="12-month variation as percentage")
    numero_indice: Decimal = Field(..., description="Base 100 continuous chain index")

    model_config = {"from_attributes": True}


class INCCHistoryResponse(BaseModel):
    """Schema representing a paginated historical series result."""

    total: int = Field(..., description="Total records matching criteria")
    skip: int = Field(..., description="Pagination offset")
    limit: int = Field(..., description="Pagination page size limit")
    sigla: Optional[str] = Field(None, description="Filtered index acronym")
    items: List[INCCRecordResponse] = Field(..., description="List of historical records")


class INCCCorrectionRequest(BaseModel):
    """Schema for requesting monetary adjustment/correction using INCC index."""

    valor_inicial: Decimal = Field(..., gt=0, description="Initial monetary value to be adjusted (> 0)")
    data_inicio: date = Field(..., description="Start reference date (e.g. 2023-01-01)")
    data_fim: date = Field(..., description="End reference date (e.g. 2024-01-01)")
    sigla: str = Field(default="INCC-M", description="Index variant to use: 'INCC-M' or 'INCC-DI'")

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


class INCCCorrectionResponse(BaseModel):
    """Schema returning monetary correction calculation results."""

    valor_inicial: Decimal = Field(..., description="Original value submitted")
    valor_corrigido: Decimal = Field(..., description="Calculated adjusted value")
    fator_correcao: Decimal = Field(..., description="Multiplication factor (indice_final / indice_inicial)")
    variacao_acumulada_percentual: Decimal = Field(..., description="Total accumulated variation in percentage")
    data_inicio_utilizada: date = Field(..., description="Effective start month used")
    data_fim_utilizada: date = Field(..., description="Effective end month used")
    indice_inicial: Decimal = Field(..., description="Starting base index (numero_indice)")
    indice_final: Decimal = Field(..., description="Ending base index (numero_indice)")
    sigla: str = Field(..., description="Index used for correction")
