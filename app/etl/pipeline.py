"""Unified ETL pipeline orchestrator for AutoINCC.

Coordinates extraction (BCB SGS), transformation (INCCProcessor), and load (INCCLoader).
"""

from datetime import date
import time
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.etl.downloader import BCBDownloader, SERIES_MAP
from app.etl.loader import INCCLoader
from app.etl.processor import INCCProcessor

logger = get_logger(__name__)


def run_etl_pipeline(
    session: Optional[Session] = None,
    series_codes: Optional[List[int]] = None,
    data_inicial: Optional[date] = None,
    data_final: Optional[date] = None,
) -> Dict[str, Any]:
    """Runs the full ETL pipeline for specified BCB series.

    Args:
        session (Optional[Session]): SQLAlchemy session. If None, creates a new one.
        series_codes (Optional[List[int]]): List of series codes to run. Defaults to [192, 7456].
        data_inicial (Optional[date]): Start date filter for extraction.
        data_final (Optional[date]): End date filter for extraction.

    Returns:
        Dict[str, Any]: Summary dictionary containing execution statistics and status.
    """
    start_time = time.time()
    series_to_run = series_codes or list(SERIES_MAP.keys())
    logger.info("Starting AutoINCC ETL pipeline for series: %s", series_to_run)

    own_session = False
    if session is None:
        session = SessionLocal()
        own_session = True

    downloader = BCBDownloader()
    loader = INCCLoader(session)

    summary: Dict[str, Any] = {
        "status": "success",
        "series_processed": {},
        "total_records_processed": 0,
        "elapsed_seconds": 0.0,
        "errors": [],
    }

    try:
        loader.ensure_baseline_dimensions()

        for serie_code in series_to_run:
            serie_info = SERIES_MAP.get(serie_code)
            if not serie_info:
                msg = f"Unknown series code: {serie_code}"
                logger.warning(msg)
                summary["errors"].append(msg)
                continue

            sigla = serie_info["sigla"]
            tipo_id = serie_info["tipo_id"]
            logger.info("Processing series %s (%s, tipo_id=%d)", serie_code, sigla, tipo_id)

            try:
                # 1. Download
                raw_data = downloader.fetch_series_raw(
                    serie_codigo=serie_code,
                    data_inicial=data_inicial,
                    data_final=data_final,
                )

                # 2. Process
                df_tempo, df_fato = INCCProcessor.process_series(
                    raw_data=raw_data,
                    tipo_id=tipo_id,
                    categoria_id=1,
                    cidade_id=1,
                    base_index=100.0,
                )

                # 3. Load / Upsert
                n_tempo = loader.upsert_dim_tempo(df_tempo)
                n_fato = loader.upsert_fato_incc(df_fato)

                summary["series_processed"][sigla] = {
                    "serie_code": serie_code,
                    "records_downloaded": len(raw_data),
                    "dim_tempo_upserted": n_tempo,
                    "fato_incc_upserted": n_fato,
                }
                summary["total_records_processed"] += n_fato

            except Exception as ex:
                err_msg = f"Failed processing series {serie_code} ({sigla}): {str(ex)}"
                logger.error(err_msg, exc_info=True)
                summary["errors"].append(err_msg)
                summary["status"] = "partial_failure" if summary["total_records_processed"] > 0 else "failed"

    finally:
        if own_session:
            session.close()

    elapsed = round(time.time() - start_time, 3)
    summary["elapsed_seconds"] = elapsed
    logger.info("ETL pipeline finished in %.3f seconds. Status: %s", elapsed, summary["status"])
    return summary
