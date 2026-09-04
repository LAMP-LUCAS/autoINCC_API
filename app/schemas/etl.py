"""Pydantic schemas for ETL trigger and execution reporting."""

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ETLTriggerRequest(BaseModel):
    """Payload for triggering on-demand ETL execution."""

    series_codes: Optional[List[int]] = Field(
        default=None,
        description="Lista opcional de códigos numéricos de séries do BCB SGS (192 para INCC-M, 7456 para INCC-DI). Se omitido, executa todas as séries configuradas.",
        examples=[[192, 7456]],
    )
    data_inicial: Optional[date] = Field(
        default=None,
        description="Data inicial opcional para recorte da extração no Banco Central (formato YYYY-MM-DD). Se omitido, extrai todo o histórico disponível.",
        examples=["2024-01-01"],
    )
    data_final: Optional[date] = Field(
        default=None,
        description="Data final opcional para recorte da extração no Banco Central (formato YYYY-MM-DD).",
        examples=["2024-12-01"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "series_codes": [192, 7456],
                "data_inicial": "2024-01-01",
                "data_final": "2024-12-01",
            }
        }
    )


class ETLTriggerResponse(BaseModel):
    """Response returned when ETL is accepted for background execution."""

    message: str = Field(..., description="Mensagem descritiva do resultado do agendamento da tarefa.", examples=["ETL task enqueued in Celery worker."])
    status: str = Field(..., description="Estado atual da requisição assíncrona ('accepted').", examples=["accepted"])
    task_id: str = Field(..., description="Identificador único UUIDv4 para rastreabilidade da tarefa no Celery/Worker.", examples=["99f448fd-75f6-4506-b160-da744025fc78"])
    triggered_at: datetime = Field(..., description="Carimbo temporal UTC de recebimento e despacho da solicitação.", examples=["2026-09-04T17:10:22.041738Z"])
    series: List[int] = Field(..., description="Lista de códigos SGS programados para download e processamento.", examples=[[192, 7456]])

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "ETL task enqueued in Celery worker.",
                "status": "accepted",
                "task_id": "99f448fd-75f6-4506-b160-da744025fc78",
                "triggered_at": "2026-09-04T17:10:22.041738Z",
                "series": [192, 7456],
            }
        }
    )

