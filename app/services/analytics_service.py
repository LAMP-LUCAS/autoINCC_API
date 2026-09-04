"""Domain service implementing analytics, overviews, seasonality, and comparative metrics."""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import math
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models import DimTempo, DimTipoIndice, FatoINCC
from app.schemas.analytics import (
    INCCAcceleration,
    INCCCompareItem,
    INCCCompareResponse,
    INCCCurrentSnapshot,
    INCCMetadataResponse,
    INCCMonthSeasonality,
    INCCOverviewResponse,
    INCCSeasonalityResponse,
    INCCSeriesMetadataItem,
    INCCStatsResponse,
)

logger = get_logger(__name__)

MESES_PT_BR = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}


def _to_decimal(val: Any, places: int = 4) -> Optional[Decimal]:
    """Safely casts numeric float/int to quantized Decimal, returning None on NaN or None."""
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        fmt = "0." + ("0" * places)
        return Decimal(str(round(f, places))).quantize(Decimal(fmt), rounding=ROUND_HALF_UP)
    except Exception:
        return None


class AnalyticsService:
    """Domain service for pre-computed, standardized economic insights and overviews."""

    @classmethod
    def get_market_overview(cls, db: Session) -> Optional[INCCOverviewResponse]:
        """Builds a consolidated market snapshot of latest INCC-M and INCC-DI observations.

        Args:
            db (Session): Active database session.

        Returns:
            Optional[INCCOverviewResponse]: Overview schema or None if no data exists.
        """
        # 1. Fetch all records for INCC-M ordered by date desc to compute rolling windows
        q_m = (
            select(FatoINCC)
            .join(DimTipoIndice, FatoINCC.tipo_id == DimTipoIndice.tipo_id)
            .where(DimTipoIndice.sigla == "INCC-M")
            .order_by(desc(FatoINCC.data_id))
            .limit(40)
        )
        records_m = db.execute(q_m).scalars().all()

        # 2. Fetch latest record for INCC-DI
        q_di = (
            select(FatoINCC)
            .join(DimTipoIndice, FatoINCC.tipo_id == DimTipoIndice.tipo_id)
            .where(DimTipoIndice.sigla == "INCC-DI")
            .order_by(desc(FatoINCC.data_id))
            .limit(1)
        )
        record_di = db.execute(q_di).scalar_one_or_none()

        if not records_m and not record_di:
            return None

        latest_m = records_m[0] if records_m else None
        ref_date = latest_m.data_id if latest_m else record_di.data_id

        # Build INCC-M Snapshot with multi-window rates (24M, 36M)
        snap_m: Optional[INCCCurrentSnapshot] = None
        accel_m: Optional[INCCAcceleration] = None

        if latest_m:
            idx_cur = float(latest_m.numero_indice)
            v_24m: Optional[float] = None
            v_36m: Optional[float] = None

            # 24-month rolling index ratio: I_t / I_{t-24} - 1
            if len(records_m) > 24:
                idx_24 = float(records_m[24].numero_indice)
                if idx_24 > 0:
                    v_24m = ((idx_cur / idx_24) - 1.0) * 100.0

            # 36-month rolling index ratio: I_t / I_{t-36} - 1
            if len(records_m) > 36:
                idx_36 = float(records_m[36].numero_indice)
                if idx_36 > 0:
                    v_36m = ((idx_cur / idx_36) - 1.0) * 100.0

            vm_pct = float(latest_m.variacao_mensal) * 100.0
            ytd_pct = float(latest_m.variacao_ytd) * 100.0 if latest_m.variacao_ytd is not None else None
            v12_pct = float(latest_m.variacao_12m) * 100.0 if latest_m.variacao_12m is not None else None

            snap_m = INCCCurrentSnapshot(
                sigla="INCC-M",
                data_id=latest_m.data_id,
                variacao_mensal_percentual=_to_decimal(vm_pct, 4) or Decimal("0.0000"),
                numero_indice=_to_decimal(idx_cur, 6) or Decimal("100.000000"),
                variacao_ytd_percentual=_to_decimal(ytd_pct, 4),
                variacao_12m_percentual=_to_decimal(v12_pct, 4),
                variacao_24m_percentual=_to_decimal(v_24m, 4),
                variacao_36m_percentual=_to_decimal(v_36m, 4),
            )

            # Acceleration metrics
            delta_prior: Optional[float] = None
            delta_year: Optional[float] = None
            if len(records_m) > 1:
                vm_prev = float(records_m[1].variacao_mensal) * 100.0
                delta_prior = vm_pct - vm_prev

            if len(records_m) > 12:
                vm_year_ago = float(records_m[12].variacao_mensal) * 100.0
                delta_year = vm_pct - vm_year_ago

            trend = "estavel"
            if delta_prior is not None:
                if delta_prior > 0.05:
                    trend = "acelerando"
                elif delta_prior < -0.05:
                    trend = "desacelerando"

            accel_m = INCCAcceleration(
                delta_mes_anterior_pontos=_to_decimal(delta_prior, 4),
                delta_ano_anterior_pontos=_to_decimal(delta_year, 4),
                tendencia=trend,
            )

        # Build INCC-DI Snapshot
        snap_di: Optional[INCCCurrentSnapshot] = None
        if record_di:
            idx_di = float(record_di.numero_indice)
            vm_di_pct = float(record_di.variacao_mensal) * 100.0
            ytd_di_pct = float(record_di.variacao_ytd) * 100.0 if record_di.variacao_ytd is not None else None
            v12_di_pct = float(record_di.variacao_12m) * 100.0 if record_di.variacao_12m is not None else None

            snap_di = INCCCurrentSnapshot(
                sigla="INCC-DI",
                data_id=record_di.data_id,
                variacao_mensal_percentual=_to_decimal(vm_di_pct, 4) or Decimal("0.0000"),
                numero_indice=_to_decimal(idx_di, 6) or Decimal("100.000000"),
                variacao_ytd_percentual=_to_decimal(ytd_di_pct, 4),
                variacao_12m_percentual=_to_decimal(v12_di_pct, 4),
                variacao_24m_percentual=None,
                variacao_36m_percentual=None,
            )

        # Spread M vs DI in percentage points
        spread_pts: Optional[Decimal] = None
        if snap_m and snap_di:
            spread_pts = snap_m.variacao_mensal_percentual - snap_di.variacao_mensal_percentual

        return INCCOverviewResponse(
            data_referencia=ref_date,
            incc_m=snap_m,
            incc_di=snap_di,
            spread_mensal_pontos=spread_pts,
            aceleracao_incc_m=accel_m,
        )

    @classmethod
    def get_comparison_series(
        cls,
        db: Session,
        data_inicio: Optional[date] = None,
        data_fim: Optional[date] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> INCCCompareResponse:
        """Constructs an aligned side-by-side time-series comparing INCC-M and INCC-DI.

        Args:
            db (Session): Database session.
            data_inicio (Optional[date]): Filter start date.
            data_fim (Optional[date]): Filter end date.
            skip (int): Pagination offset.
            limit (int): Pagination limit.

        Returns:
            INCCCompareResponse: Unified chronological comparison list.
        """
        query = (
            select(
                FatoINCC.data_id,
                DimTempo.ano,
                DimTempo.mes,
                DimTipoIndice.sigla,
                FatoINCC.variacao_mensal,
                FatoINCC.numero_indice,
            )
            .join(DimTempo, FatoINCC.data_id == DimTempo.data_id)
            .join(DimTipoIndice, FatoINCC.tipo_id == DimTipoIndice.tipo_id)
        )

        if data_inicio:
            dt_s = date(data_inicio.year, data_inicio.month, 1)
            query = query.where(FatoINCC.data_id >= dt_s)
        if data_fim:
            dt_e = date(data_fim.year, data_fim.month, 1)
            query = query.where(FatoINCC.data_id <= dt_e)

        query = query.order_by(FatoINCC.data_id.asc())
        rows = db.execute(query).all()

        # Group by date_id in a dictionary
        pivot: Dict[date, Dict[str, Any]] = {}
        for r in rows:
            d_id = r.data_id
            if d_id not in pivot:
                pivot[d_id] = {
                    "data_id": d_id,
                    "ano": r.ano,
                    "mes": r.mes,
                    "incc_m_var": None,
                    "incc_m_idx": None,
                    "incc_di_var": None,
                    "incc_di_idx": None,
                }
            if r.sigla == "INCC-M":
                pivot[d_id]["incc_m_var"] = float(r.variacao_mensal) * 100.0
                pivot[d_id]["incc_m_idx"] = float(r.numero_indice)
            elif r.sigla == "INCC-DI":
                pivot[d_id]["incc_di_var"] = float(r.variacao_mensal) * 100.0
                pivot[d_id]["incc_di_idx"] = float(r.numero_indice)

        sorted_dates = sorted(pivot.keys())
        total = len(sorted_dates)
        paged_dates = sorted_dates[skip : skip + limit]

        items: List[INCCCompareItem] = []
        for d in paged_dates:
            row = pivot[d]
            vm = row["incc_m_var"]
            vdi = row["incc_di_var"]

            spread: Optional[Decimal] = None
            maior: Optional[str] = None

            if vm is not None and vdi is not None:
                spread = _to_decimal(vm - vdi, 4)
                if vm > vdi:
                    maior = "INCC-M"
                elif vdi > vm:
                    maior = "INCC-DI"
                else:
                    maior = "EMPATE"
            elif vm is not None:
                maior = "INCC-M"
            elif vdi is not None:
                maior = "INCC-DI"

            items.append(
                INCCCompareItem(
                    data_id=d,
                    ano=row["ano"],
                    mes=row["mes"],
                    incc_m_variacao_percentual=_to_decimal(vm, 4),
                    incc_m_indice=_to_decimal(row["incc_m_idx"], 6),
                    incc_di_variacao_percentual=_to_decimal(vdi, 4),
                    incc_di_indice=_to_decimal(row["incc_di_idx"], 6),
                    spread_variacao_pontos=spread,
                    variante_maior_taxa=maior,
                )
            )

        return INCCCompareResponse(
            total_periodos=total,
            data_inicio=data_inicio,
            data_fim=data_fim,
            items=items,
        )

    @classmethod
    def get_seasonality_analysis(cls, db: Session, sigla: str = "INCC-M") -> Optional[INCCSeasonalityResponse]:
        """Calculates historical calendar month seasonality matrix (January to December).

        Args:
            db (Session): Database session.
            sigla (str): Index variant ('INCC-M' or 'INCC-DI').

        Returns:
            Optional[INCCSeasonalityResponse]: Seasonality report.
        """
        sigla_upper = sigla.upper()
        query = (
            select(DimTempo.mes, DimTempo.ano, FatoINCC.variacao_mensal)
            .join(DimTempo, FatoINCC.data_id == DimTempo.data_id)
            .join(DimTipoIndice, FatoINCC.tipo_id == DimTipoIndice.tipo_id)
            .where(DimTipoIndice.sigla == sigla_upper)
            .order_by(DimTempo.ano.asc(), DimTempo.mes.asc())
        )
        rows = db.execute(query).all()

        if not rows:
            return None

        # Build month buckets
        month_buckets: Dict[int, List[float]] = {m: [] for m in range(1, 13)}
        years = set()
        for r in rows:
            rate_pct = float(r.variacao_mensal) * 100.0
            month_buckets[r.mes].append(rate_pct)
            years.add(r.ano)

        meses_stats: List[INCCMonthSeasonality] = []
        for m in range(1, 13):
            rates = month_buckets[m]
            if not rates:
                continue

            arr = np.array(rates)
            media = float(np.mean(arr))
            mediana = float(np.median(arr))
            std_dev = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0
            min_v = float(np.min(arr))
            max_v = float(np.max(arr))
            prob_alta = (float(np.sum(arr > 0.0)) / len(arr)) * 100.0

            meses_stats.append(
                INCCMonthSeasonality(
                    mes=m,
                    nome_mes=MESES_PT_BR.get(m, f"Mês {m}"),
                    total_anos=len(rates),
                    media_variacao_percentual=_to_decimal(media, 4) or Decimal("0.0000"),
                    mediana_variacao_percentual=_to_decimal(mediana, 4) or Decimal("0.0000"),
                    desvio_padrao_pontos=_to_decimal(std_dev, 4) or Decimal("0.0000"),
                    minima_variacao_percentual=_to_decimal(min_v, 4) or Decimal("0.0000"),
                    maxima_variacao_percentual=_to_decimal(max_v, 4) or Decimal("0.0000"),
                    probabilidade_alta_percentual=_to_decimal(prob_alta, 2) or Decimal("0.00"),
                )
            )

        y_min = min(years) if years else 0
        y_max = max(years) if years else 0
        periodo = f"{y_min} a {y_max}" if y_min != y_max else str(y_min)

        return INCCSeasonalityResponse(
            sigla=sigla_upper,
            periodo_historico=periodo,
            total_observacoes=len(rows),
            meses=meses_stats,
        )

    @classmethod
    def get_series_statistics(cls, db: Session, sigla: str = "INCC-M") -> Optional[INCCStatsResponse]:
        """Calculates global statistical summary metrics for an index variant.

        Args:
            db (Session): Database session.
            sigla (str): Index variant ('INCC-M' or 'INCC-DI').

        Returns:
            Optional[INCCStatsResponse]: Statistical summary or None.
        """
        sigla_upper = sigla.upper()
        query = (
            select(FatoINCC.data_id, FatoINCC.variacao_mensal)
            .join(DimTipoIndice, FatoINCC.tipo_id == DimTipoIndice.tipo_id)
            .where(DimTipoIndice.sigla == sigla_upper)
            .order_by(FatoINCC.data_id.asc())
        )
        rows = db.execute(query).all()

        if not rows:
            return None

        rates = [float(r.variacao_mensal) * 100.0 for r in rows]
        dates = [r.data_id for r in rows]
        arr = np.array(rates)

        total_obs = len(arr)
        d_start = dates[0]
        d_end = dates[-1]

        media = float(np.mean(arr))
        mediana = float(np.median(arr))
        std_dev = float(np.std(arr, ddof=1)) if total_obs > 1 else 0.0
        # Annualized volatility = monthly std dev * sqrt(12)
        vol_anualizada = std_dev * math.sqrt(12.0)

        max_idx = int(np.argmax(arr))
        min_idx = int(np.argmin(arr))

        return INCCStatsResponse(
            sigla=sigla_upper,
            total_observacoes=total_obs,
            data_inicio=d_start,
            data_fim=d_end,
            media_mensal_percentual=_to_decimal(media, 4) or Decimal("0.0000"),
            mediana_mensal_percentual=_to_decimal(mediana, 4) or Decimal("0.0000"),
            desvio_padrao_mensal_pontos=_to_decimal(std_dev, 4) or Decimal("0.0000"),
            volatilidade_anualizada_percentual=_to_decimal(vol_anualizada, 4) or Decimal("0.0000"),
            recorde_alta_percentual=_to_decimal(arr[max_idx], 4) or Decimal("0.0000"),
            recorde_alta_data=dates[max_idx],
            recorde_baixa_percentual=_to_decimal(arr[min_idx], 4) or Decimal("0.0000"),
            recorde_baixa_data=dates[min_idx],
        )

    @classmethod
    def get_series_metadata(cls) -> INCCMetadataResponse:
        """Returns official technical catalog, survey windows and methodological notes."""
        series_items = [
            INCCSeriesMetadataItem(
                sigla="INCC-M",
                codigo_bcb=192,
                nome_oficial="Índice Nacional de Custo da Construção - Mercado",
                fonte_primaria="FGV IBRE / Banco Central do Brasil (SGS)",
                instituto_responsavel="Fundação Getulio Vargas (FGV IBRE)",
                janela_coleta="Do dia 21 do mês anterior ao dia 20 do mês de referência",
                periodicidade="Mensal",
                inicio_serie="1944",
                metodologia=(
                    "Mede a evolução dos custos de construções habitacionais em 7 capitais "
                    "(SP, RJ, BH, POA, Salvador, Recife, Brasília). Abrange Materiais e Equipamentos, "
                    "Serviços e Mão de Obra. Utilizado preferencialmente para reajuste de contratos na planta."
                ),
            ),
            INCCSeriesMetadataItem(
                sigla="INCC-DI",
                codigo_bcb=7456,
                nome_oficial="Índice Nacional de Custo da Construção - Disponibilidade Interna",
                fonte_primaria="FGV IBRE / Banco Central do Brasil (SGS)",
                instituto_responsavel="Fundação Getulio Vargas (FGV IBRE)",
                janela_coleta="Do primeiro ao último dia do mês civil de referência",
                periodicidade="Mensal",
                inicio_serie="1944",
                metodologia=(
                    "Subíndice do IGP-DI. Mede a variação de custos no mês calendário fechado. "
                    "Utilizado em balanços corporativos, análises contábeis e liquidações contratuais."
                ),
            ),
        ]

        notas = [
            "Revisão Metodológica (Julho/2023): O FGV IBRE introduziu novas estruturas de ponderação, "
            "subdividindo o índice em três padrões construtivos distintos (Econômico, Médio e Alto) e "
            "atualizando pesos relativos de insumos modernos (aço, alumínio, instalações).",
            "Convenção de Encadeamento: O número-índice base 100 contínuo fornecido pelo AutoINCC é encadeado "
            "pelo produtório exato das variações mensais oficiais publicadas pelo Banco Central.",
            "Integridade de Dados: O AutoINCC aplica UPSERT idempotente e auditoria em todas as coletas.",
        ]

        return INCCMetadataResponse(series=series_items, notas_metodologicas=notas)
