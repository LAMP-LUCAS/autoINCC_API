"""ETL administrative trigger endpoint with Celery dispatch and BackgroundTasks fallback."""

from datetime import datetime, timezone
import uuid
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, status

from app.api.deps import verify_api_key
from app.core.logging import get_logger
from app.etl.pipeline import run_etl_pipeline
from app.schemas.etl import ETLTriggerRequest, ETLTriggerResponse
from app.tasks.etl_tasks import run_etl_celery_task

logger = get_logger(__name__)

router = APIRouter(prefix="/etl", tags=["ETL"])


def _background_etl_worker(
    task_id: str,
    series_codes: Optional[list],
    data_inicial: Optional[object],
    data_final: Optional[object],
) -> None:
    """Fallback in-process worker executing ETL if Celery broker is offline.

    Args:
        task_id (str): Unique background job identifier.
        series_codes (Optional[list]): List of series to extract.
        data_inicial (Optional[object]): Starting date.
        data_final (Optional[object]): Ending date.
    """
    logger.info("Fallback BackgroundTasks worker %s started.", task_id)
    try:
        summary = run_etl_pipeline(
            series_codes=series_codes,
            data_inicial=data_inicial,
            data_final=data_final,
        )
        logger.info("Fallback BackgroundTasks worker %s finished: %s", task_id, summary)
    except Exception as ex:
        logger.error("Fallback BackgroundTasks worker %s failed: %s", task_id, ex, exc_info=True)


@router.post(
    "/trigger",
    response_model=ETLTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger the ETL pipeline asynchronously via Celery",
    description="Dispatches an asynchronous extraction and transformation task to Celery worker via Redis queue. Requires X-API-Key header.",
)
def trigger_etl(
    payload: Optional[ETLTriggerRequest] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    api_key: str = Depends(verify_api_key),
) -> ETLTriggerResponse:
    """Asynchronously triggers the AutoINCC ETL pipeline via Celery worker (with fallback)."""
    now = datetime.now(timezone.utc)
    series = payload.series_codes if payload and payload.series_codes else [192, 7456]
    d_start = payload.data_inicial if payload else None
    d_end = payload.data_final if payload else None

    d_start_str = d_start.isoformat() if d_start else None
    d_end_str = d_end.isoformat() if d_end else None

    task_id: str
    status_msg: str

    try:
        # 1. Attempt dispatch to Celery queue via Redis
        async_result = run_etl_celery_task.delay(
            series_codes=series,
            data_inicial_str=d_start_str,
            data_final_str=d_end_str,
        )
        task_id = str(async_result.id)
        status_msg = "ETL task enqueued in Celery worker."
        logger.info("Enqueued Celery task %s for series %s", task_id, series)

    except Exception as exc:
        # 2. Resilient fallback to FastAPI BackgroundTasks if Celery/Redis is not running
        task_id = str(uuid.uuid4())
        status_msg = f"Celery broker unavailable ({exc}). Dispatched via BackgroundTasks fallback."
        logger.warning(status_msg)
        background_tasks.add_task(
            _background_etl_worker,
            task_id=task_id,
            series_codes=series,
            data_inicial=d_start,
            data_final=d_end,
        )

    return ETLTriggerResponse(
        message=status_msg,
        status="accepted",
        task_id=task_id,
        triggered_at=now,
        series=series,
    )
