"""INCC endpoints: latest, historical time series, and monetary correction with Redis caching."""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.cache import get_cache, set_cache
from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import DimTempo, DimTipoIndice, FatoINCC
from app.schemas.analytics import (
    INCCCompareResponse,
    INCCMetadataResponse,
    INCCOverviewResponse,
    INCCSeasonalityResponse,
    INCCStatsResponse,
)
from app.schemas.incc import (
    INCCHistoryResponse,
    INCCRecordResponse,
    INCCCorrectionRequest,
    INCCCorrectionResponse,
)
from app.services.analytics_service import AnalyticsService

logger = get_logger(__name__)

router = APIRouter(prefix="/incc", tags=["INCC"])


def _clean_decimal(val: Any) -> Optional[Decimal]:
    """Safely converts input to Decimal, converting None, NaN, and Infs to None."""
    if val is None:
        return None
    try:
        d = Decimal(str(val))
        if d.is_nan() or d.is_infinite():
            return None
        return d
    except Exception:
        return None


def _format_record(fato: FatoINCC) -> INCCRecordResponse:
    """Helper to convert FatoINCC ORM object to INCCRecordResponse schema.

    Args:
        fato (FatoINCC): Database fact row with joined dimensions.

    Returns:
        INCCRecordResponse: Validated Pydantic schema with percentage translations.
    """
    v_m = _clean_decimal(fato.variacao_mensal) or Decimal("0.000000")
    v_ytd = _clean_decimal(fato.variacao_ytd)
    v_12m = _clean_decimal(fato.variacao_12m)
    num_idx = _clean_decimal(fato.numero_indice) or Decimal("100.000000")

    return INCCRecordResponse(
        data_id=fato.data_id,
        ano=fato.tempo.ano,
        mes=fato.tempo.mes,
        nome_mes=fato.tempo.nome_mes,
        sigla=fato.tipo_indice.sigla,
        fonte=fato.tipo_indice.fonte,
        variacao_mensal=v_m,
        variacao_mensal_percentual=round(v_m * Decimal("100"), 4),
        variacao_ytd=v_ytd,
        variacao_ytd_percentual=round(v_ytd * Decimal("100"), 4) if v_ytd is not None else None,
        variacao_12m=v_12m,
        variacao_12m_percentual=round(v_12m * Decimal("100"), 4) if v_12m is not None else None,
        numero_indice=num_idx,
    )


@router.get(
    "/latest",
    response_model=INCCRecordResponse,
    summary="Get the most recent consolidated INCC index",
    description="Returns the latest calculated index and variation rates for the specified series (cached in Redis).",
)
def get_latest_incc(
    sigla: str = Query(
        default="INCC-M",
        description="Index variation acronym ('INCC-M' or 'INCC-DI')",
        pattern="^(?i)(INCC-M|INCC-DI)$",
    ),
    db: Session = Depends(get_db),
) -> INCCRecordResponse:
    """Retrieves the latest available month record for a given index variant (with Redis cache)."""
    sigla_upper = sigla.upper()
    cache_key = f"incc:latest:{sigla_upper}"

    # 1. Check Redis cache
    cached = get_cache(cache_key)
    if cached:
        return INCCRecordResponse(**cached)

    # 2. Database query on cache miss
    query = (
        select(FatoINCC)
        .join(DimTipoIndice, FatoINCC.tipo_id == DimTipoIndice.tipo_id)
        .where(DimTipoIndice.sigla == sigla_upper)
        .order_by(desc(FatoINCC.data_id))
        .limit(1)
    )

    record = db.execute(query).scalar_one_or_none()

    if not record:
        logger.warning("No records found in database for index: %s", sigla_upper)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No data found for index '{sigla_upper}'. Run the ETL pipeline to populate the database.",
        )

    formatted = _format_record(record)
    # 3. Store in Redis cache
    set_cache(cache_key, formatted.model_dump(mode="json"), ttl_seconds=settings.CACHE_TTL_SECONDS)
    return formatted


@router.get(
    "/history",
    response_model=INCCHistoryResponse,
    summary="Get historical time series filtered by date interval",
    description="Returns a paginated list of observations between `data_inicio` and `data_fim` (cached in Redis).",
)
def get_incc_history(
    data_inicio: date = Query(..., description="Start date (YYYY-MM-DD)"),
    data_fim: date = Query(..., description="End date (YYYY-MM-DD)"),
    sigla: Optional[str] = Query(
        default="INCC-M",
        description="Index variant ('INCC-M' or 'INCC-DI')",
    ),
    skip: int = Query(default=0, ge=0, description="Offset pagination"),
    limit: int = Query(default=100, ge=1, le=1000, description="Items limit per page"),
    db: Session = Depends(get_db),
) -> INCCHistoryResponse:
    """Returns chronological series observations within the specified date interval (with Redis cache)."""
    if data_fim < data_inicio:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="data_fim cannot be prior to data_inicio",
        )

    # Convert to first day of each month for exact matching
    dt_start = date(data_inicio.year, data_inicio.month, 1)
    dt_end = date(data_fim.year, data_fim.month, 1)
    sigla_upper = sigla.upper() if sigla else "ALL"

    cache_key = f"incc:history:{dt_start}:{dt_end}:{sigla_upper}:{skip}:{limit}"
    cached = get_cache(cache_key)
    if cached:
        return INCCHistoryResponse(**cached)

    base_query = (
        select(FatoINCC)
        .join(DimTipoIndice, FatoINCC.tipo_id == DimTipoIndice.tipo_id)
        .where(FatoINCC.data_id >= dt_start)
        .where(FatoINCC.data_id <= dt_end)
    )

    if sigla:
        base_query = base_query.where(DimTipoIndice.sigla == sigla.upper())

    # Count total matching rows
    count_query = select(func.count()).select_from(base_query.subquery())
    total_count = db.execute(count_query).scalar_one()

    # Paginated ordered query
    records_query = (
        base_query.order_by(FatoINCC.data_id.asc(), FatoINCC.tipo_id.asc())
        .offset(skip)
        .limit(limit)
    )
    records = db.execute(records_query).scalars().all()

    items = [_format_record(r) for r in records]

    response_obj = INCCHistoryResponse(
        total=total_count,
        skip=skip,
        limit=limit,
        sigla=sigla.upper() if sigla else None,
        items=items,
    )

    set_cache(cache_key, response_obj.model_dump(mode="json"), ttl_seconds=settings.CACHE_TTL_SECONDS)
    return response_obj


@router.post(
    "/correction",
    response_model=INCCCorrectionResponse,
    summary="Calculate monetary correction between two dates",
    description="Calculates adjusted value using cumulative index variation: Factor = Index_Final / Index_Initial.",
)
def calculate_incc_correction(
    payload: INCCCorrectionRequest,
    db: Session = Depends(get_db),
) -> INCCCorrectionResponse:
    """Calculates inflation adjustment for contracts and budgets using the INCC continuous chain index."""
    # Normalize input dates to first of month
    dt_start = date(payload.data_inicio.year, payload.data_inicio.month, 1)
    dt_end = date(payload.data_fim.year, payload.data_fim.month, 1)

    sigla_upper = payload.sigla.upper()

    # Query initial index
    q_start = (
        select(FatoINCC)
        .join(DimTipoIndice, FatoINCC.tipo_id == DimTipoIndice.tipo_id)
        .where(DimTipoIndice.sigla == sigla_upper)
        .where(FatoINCC.data_id == dt_start)
    )
    fato_start = db.execute(q_start).scalar_one_or_none()

    if not fato_start:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Initial index for date '{dt_start.strftime('%Y-%m')}' and index '{sigla_upper}' was not found. "
                "Ensure data has been ingested for this period."
            ),
        )

    # Query final index
    q_end = (
        select(FatoINCC)
        .join(DimTipoIndice, FatoINCC.tipo_id == DimTipoIndice.tipo_id)
        .where(DimTipoIndice.sigla == sigla_upper)
        .where(FatoINCC.data_id == dt_end)
    )
    fato_end = db.execute(q_end).scalar_one_or_none()

    if not fato_end:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Final index for date '{dt_end.strftime('%Y-%m')}' and index '{sigla_upper}' was not found. "
                "Ensure data has been ingested for this period."
            ),
        )

    idx_start = Decimal(str(fato_start.numero_indice))
    idx_end = Decimal(str(fato_end.numero_indice))

    if idx_start <= Decimal("0"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Initial index is zero or negative, cannot compute correction factor.",
        )

    # Fator = Indice_Final / Indice_Inicial
    fator = (idx_end / idx_start).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)

    # Valor Corrigido = Valor Inicial * Fator
    valor_corrigido = (payload.valor_inicial * fator).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Variação acumulada no período (%) = (Fator - 1) * 100
    variacao_acumulada_percentual = ((fator - Decimal("1.0")) * Decimal("100")).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )

    return INCCCorrectionResponse(
        valor_inicial=payload.valor_inicial.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        valor_corrigido=valor_corrigido,
        fator_correcao=fator.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP),
        variacao_acumulada_percentual=variacao_acumulada_percentual,
        data_inicio_utilizada=dt_start,
        data_fim_utilizada=dt_end,
        indice_inicial=idx_start,
        indice_final=idx_end,
        sigla=sigla_upper,
    )


@router.get(
    "/overview",
    response_model=INCCOverviewResponse,
    summary="Get current market overview and key dynamics",
    description="Returns latest INCC-M and INCC-DI rates, spreads, rolling returns (24M, 36M), and acceleration trend.",
)
def get_market_overview(
    db: Session = Depends(get_db),
) -> INCCOverviewResponse:
    """Consolidated market overview for latest published period (cached in Redis)."""
    cache_key = "incc:overview"
    cached = get_cache(cache_key)
    if cached:
        return INCCOverviewResponse(**cached)

    overview = AnalyticsService.get_market_overview(db)
    if not overview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No INCC observations found to generate market overview. Run ETL pipeline.",
        )

    set_cache(cache_key, overview.model_dump(mode="json"), ttl_seconds=settings.CACHE_TTL_SECONDS)
    return overview


@router.get(
    "/compare",
    response_model=INCCCompareResponse,
    summary="Compare INCC-M and INCC-DI side-by-side",
    description="Returns aligned monthly observations for both variants with calculated spread and dominance.",
)
def compare_incc_variants(
    data_inicio: Optional[date] = Query(default=None, description="Filter start date (YYYY-MM-DD)"),
    data_fim: Optional[date] = Query(default=None, description="Filter end date (YYYY-MM-DD)"),
    skip: int = Query(default=0, ge=0, description="Offset pagination"),
    limit: int = Query(default=100, ge=1, le=1000, description="Page limit"),
    db: Session = Depends(get_db),
) -> INCCCompareResponse:
    """Historical side-by-side comparison of INCC-M and INCC-DI with spread calculation."""
    if data_inicio and data_fim and data_fim < data_inicio:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="data_fim cannot be prior to data_inicio",
        )

    dt_s_str = data_inicio.strftime("%Y-%m-%d") if data_inicio else "ALL"
    dt_e_str = data_fim.strftime("%Y-%m-%d") if data_fim else "ALL"
    cache_key = f"incc:compare:{dt_s_str}:{dt_e_str}:{skip}:{limit}"

    cached = get_cache(cache_key)
    if cached:
        return INCCCompareResponse(**cached)

    result = AnalyticsService.get_comparison_series(
        db=db,
        data_inicio=data_inicio,
        data_fim=data_fim,
        skip=skip,
        limit=limit,
    )

    set_cache(cache_key, result.model_dump(mode="json"), ttl_seconds=settings.CACHE_TTL_SECONDS)
    return result


@router.get(
    "/analytics/seasonality",
    response_model=INCCSeasonalityResponse,
    summary="Get historical calendar month seasonality matrix",
    description="Computes 12-month historical statistics (mean, median, standard deviation, high probability) for an index variant.",
)
def get_seasonality_analysis(
    sigla: str = Query(
        default="INCC-M",
        description="Index variation acronym ('INCC-M' or 'INCC-DI')",
        pattern="^(?i)(INCC-M|INCC-DI)$",
    ),
    db: Session = Depends(get_db),
) -> INCCSeasonalityResponse:
    """Historical seasonality distribution across months of the year."""
    sigla_upper = sigla.upper()
    cache_key = f"incc:seasonality:{sigla_upper}"

    cached = get_cache(cache_key)
    if cached:
        return INCCSeasonalityResponse(**cached)

    seasonality = AnalyticsService.get_seasonality_analysis(db=db, sigla=sigla_upper)
    if not seasonality:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No observations found for index '{sigla_upper}' to compute seasonality.",
        )

    set_cache(cache_key, seasonality.model_dump(mode="json"), ttl_seconds=86400)
    return seasonality


@router.get(
    "/analytics/stats",
    response_model=INCCStatsResponse,
    summary="Get aggregated statistical metrics for an index variant",
    description="Calculates overall distribution metrics, annualized volatility, and historical all-time highs and lows.",
)
def get_series_statistics(
    sigla: str = Query(
        default="INCC-M",
        description="Index variation acronym ('INCC-M' or 'INCC-DI')",
        pattern="^(?i)(INCC-M|INCC-DI)$",
    ),
    db: Session = Depends(get_db),
) -> INCCStatsResponse:
    """Statistical summary metrics, annualized volatility, and historical records."""
    sigla_upper = sigla.upper()
    cache_key = f"incc:stats:{sigla_upper}"

    cached = get_cache(cache_key)
    if cached:
        return INCCStatsResponse(**cached)

    stats_data = AnalyticsService.get_series_statistics(db=db, sigla=sigla_upper)
    if not stats_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No observations found for index '{sigla_upper}' to compute statistics.",
        )

    set_cache(cache_key, stats_data.model_dump(mode="json"), ttl_seconds=86400)
    return stats_data


@router.get(
    "/metadata",
    response_model=INCCMetadataResponse,
    summary="Get technical catalog, collection windows, and methodological notes",
    description="Returns official metadata, primary sources, collection windows, and methodological revision history.",
)
def get_series_metadata() -> INCCMetadataResponse:
    """Catalog metadata and governance documentation for the AutoINCC series."""
    cache_key = "incc:metadata"
    cached = get_cache(cache_key)
    if cached:
        return INCCMetadataResponse(**cached)

    metadata = AnalyticsService.get_series_metadata()
    set_cache(cache_key, metadata.model_dump(mode="json"), ttl_seconds=86400)
    return metadata

