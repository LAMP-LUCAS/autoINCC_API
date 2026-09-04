"""Schemas package for AutoINCC."""

from app.schemas.incc import (
    INCCRecordResponse,
    INCCHistoryResponse,
    INCCCorrectionRequest,
    INCCCorrectionResponse,
)
from app.schemas.etl import ETLTriggerRequest, ETLTriggerResponse
from app.schemas.analytics import (
    INCCCurrentSnapshot,
    INCCAcceleration,
    INCCOverviewResponse,
    INCCCompareItem,
    INCCCompareResponse,
    INCCMonthSeasonality,
    INCCSeasonalityResponse,
    INCCStatsResponse,
    INCCSeriesMetadataItem,
    INCCMetadataResponse,
)

__all__ = [
    "INCCRecordResponse",
    "INCCHistoryResponse",
    "INCCCorrectionRequest",
    "INCCCorrectionResponse",
    "ETLTriggerRequest",
    "ETLTriggerResponse",
    "INCCCurrentSnapshot",
    "INCCAcceleration",
    "INCCOverviewResponse",
    "INCCCompareItem",
    "INCCCompareResponse",
    "INCCMonthSeasonality",
    "INCCSeasonalityResponse",
    "INCCStatsResponse",
    "INCCSeriesMetadataItem",
    "INCCMetadataResponse",
]
