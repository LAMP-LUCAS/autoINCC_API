"""Celery background tasks for AutoINCC ETL pipeline execution."""

from datetime import date
from typing import Any, Dict, List, Optional
from app.core.cache import invalidate_cache_pattern
from app.core.logging import get_logger
from app.etl.pipeline import run_etl_pipeline
from app.tasks.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(
    bind=True,
    name="tasks.run_etl_pipeline",
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
)
def run_etl_celery_task(
    self: Any,
    series_codes: Optional[List[int]] = None,
    data_inicial_str: Optional[str] = None,
    data_final_str: Optional[str] = None,
) -> Dict[str, Any]:
    """Celery task executing the AutoINCC ETL extraction, transformation, and load.

    Args:
        self: Task execution instance.
        series_codes (Optional[List[int]]): List of series to extract.
        data_inicial_str (Optional[str]): Start date in 'YYYY-MM-DD' format.
        data_final_str (Optional[str]): End date in 'YYYY-MM-DD' format.

    Returns:
        Dict[str, Any]: Execution statistics summary.
    """
    task_id = self.request.id or "direct"
    logger.info("Celery task %s initiated. Running AutoINCC ETL pipeline...", task_id)

    d_start = date.fromisoformat(data_inicial_str) if data_inicial_str else None
    d_end = date.fromisoformat(data_final_str) if data_final_str else None

    summary = run_etl_pipeline(
        series_codes=series_codes,
        data_inicial=d_start,
        data_final=d_end,
    )

    # Invalidate cached endpoints so API immediately reflects updated data
    invalidated_keys = invalidate_cache_pattern("incc:*")
    summary["invalidated_cache_keys"] = invalidated_keys

    logger.info("Celery task %s completed successfully: %s", task_id, summary)
    return summary
