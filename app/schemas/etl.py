"""Pydantic schemas for ETL trigger and execution reporting."""

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ETLTriggerRequest(BaseModel):
    """Payload for triggering on-demand ETL execution."""

    series_codes: Optional[List[int]] = Field(
        default=None,
        description="Optional list of BCB series codes (192, 7456). If omitted, runs all configured.",
    )
    data_inicial: Optional[date] = Field(
        default=None,
        description="Optional start date for filtering BCB download.",
    )
    data_final: Optional[date] = Field(
        default=None,
        description="Optional end date for filtering BCB download.",
    )


class ETLTriggerResponse(BaseModel):
    """Response returned when ETL is accepted for background execution."""

    message: str = Field(..., description="Status message")
    status: str = Field(..., description="Job state (e.g. accepted, running)")
    task_id: str = Field(..., description="Unique job execution tracking ID")
    triggered_at: datetime = Field(..., description="Timestamp when task was queued")
    series: List[int] = Field(..., description="Series scheduled for extraction")
