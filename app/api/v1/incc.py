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
    summary="Obter o índice mais recente consolidado com taxas acumuladas",
    response_description="Registro do mês mais recente consolidado com taxas mensal, YTD, 12M e número-índice.",
    responses={
        200: {"description": "Índice mais recente retornado com sucesso (via cache Redis ou PostgreSQL)."},
        404: {"description": "Nenhum dado encontrado para a variante solicitada. Execute o pipeline de ETL."},
        422: {"description": "Parâmetro 'sigla' inválido (deve ser 'INCC-M' ou 'INCC-DI')."},
    },
    description="""
### 🎯 O que resolve
Fornece o dado inflacionário mais recente da construção civil para balizamento imediato de custos, precificação de novos contratos, fechamento de relatórios contábeis e medições mensais de obra.

### 📥 Parâmetros de Entrada
- **`sigla`** *(string, opcional, padrão: `INCC-M`)*:
  Identificador da série desejada. Aceita:
  - `INCC-M`: Coletado do dia 21 do mês anterior ao dia 20 do mês de referência (padrão de mercado para obras).
  - `INCC-DI`: Coletado do dia 1º ao dia 30/31 do mês civil (fechamento contábil).

### 📤 O que é retornado
Objeto `INCCRecordResponse` contendo:
- `data_id`: Data de referência do mês (sempre YYYY-MM-01).
- `variacao_mensal_percentual`: Taxa do mês em percentual (ex: `0.6100` = 0,61%).
- `variacao_ytd_percentual`: Acumulado no ano corrente até o mês (Year-to-Date).
- `variacao_12m_percentual`: Acumulado móvel nos últimos 12 meses.
- `numero_indice`: Número-índice base 100 móvel contínua encadeado.

### 💡 Aplicação Prática no Setor AEC
- **Medições de Empreiteiros:** Atualização imediata dos índices de reajuste mensal de contratos de construção.
- **Dashboards de Viabilidade:** Alimentação de painéis de BI de incorporadoras e construtoras sem necessidade de cálculo manual.

### ⚡ Estratégia de Cache e Resiliência
- **Chave Redis:** `incc:latest:{sigla}`
- **TTL:** 3.600 segundos (1 hora).
- **Invalidação:** Automática após cada ciclo de ingestão do ETL.
""",
)
def get_latest_incc(
    sigla: str = Query(
        default="INCC-M",
        description="Sigla da variante do índice ('INCC-M' ou 'INCC-DI')",
        pattern="^(?i)(INCC-M|INCC-DI)$",
        examples=["INCC-M"],
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
    summary="Consultar série temporal histórica com filtros e paginação",
    response_description="Lista paginada cronológica de observações mensais no período solicitado.",
    responses={
        200: {"description": "Série temporal histórica retornada com sucesso."},
        422: {"description": "Erro de validação: 'data_fim' anterior a 'data_inicio' ou parâmetros fora dos limites."},
    },
    description="""
### 🎯 O que resolve
Permite extrair fatias temporais da série histórica para estudos de viabilidade, gráficos de evolução de preços, análises retroativas de custos de obras e calibração de modelos orçamentários.

### 📥 Parâmetros de Entrada
- **`data_inicio`** *(date, obrigatório)*: Data inicial do período desejado (formato `YYYY-MM-DD`).
- **`data_fim`** *(date, obrigatório)*: Data final do período desejado (formato `YYYY-MM-DD`). Deve ser igual ou posterior à data de início.
- **`sigla`** *(string, opcional, padrão: `INCC-M`)*: Filtrar por variante (`INCC-M` ou `INCC-DI`). Se omitido, pode trazer todas.
- **`skip`** *(int, opcional, padrão: 0)*: Deslocamento (offset) para paginação.
- **`limit`** *(int, opcional, padrão: 100, máx: 1000)*: Quantidade máxima de registros retornados por página.

### 📤 O que é retornado
Objeto `INCCHistoryResponse` contendo:
- `total`: Contagem total de registros que satisfazem aos critérios de busca.
- `skip` e `limit`: Parâmetros de paginação refletidos.
- `items`: Lista cronológica de observações com taxas mensais, acumulados e número-índice contínuo.

### 💡 Aplicação Prática no Setor AEC
- **Curva S e Orçamento Paramétrico:** Cruzamento do avanço físico-financeiro planejado com o encadeamento real do INCC ocorrido durante os anos da construção.
- **Perícias Contratuais:** Levantamento do histórico oficial para conferência de cálculos de reajustes passados.

### ⚡ Estratégia de Cache e Resiliência
- **Chave Redis:** `incc:history:{dt_start}:{dt_end}:{sigla}:{skip}:{limit}`
- **TTL:** 3.600 segundos (1 hora).
""",
)
def get_incc_history(
    data_inicio: date = Query(..., description="Data inicial do período (YYYY-MM-DD)", examples=["2023-01-01"]),
    data_fim: date = Query(..., description="Data final do período (YYYY-MM-DD)", examples=["2024-06-01"]),
    sigla: Optional[str] = Query(
        default="INCC-M",
        description="Variante do índice ('INCC-M' ou 'INCC-DI')",
        examples=["INCC-M"],
    ),
    skip: int = Query(default=0, ge=0, description="Deslocamento de paginação (offset)", examples=[0]),
    limit: int = Query(default=100, ge=1, le=1000, description="Quantidade máxima de itens por página", examples=[100]),
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
    summary="Calcular correção monetária e reajuste contratual entre duas datas",
    response_description="Resultado detalhado da correção monetária com fator multiplicador e variação acumulada.",
    responses={
        200: {"description": "Cálculo de correção monetária processado com sucesso."},
        404: {"description": "Índice inicial ou final não localizado para as datas especificadas."},
        422: {"description": "Payload inválido: valor inicial negativo ou data final anterior à inicial."},
        500: {"description": "Erro de cálculo interno: índice inicial nulo ou inconsistente."},
    },
    description="""
### 🎯 O que resolve
Automatiza com 100% de precisão matemática o cálculo de reajuste monetário de contratos de venda de imóveis na planta, parcelas de financiamento imobiliário direto com construtoras e orçamentos de obras públicas ou privadas.

### 📥 Parâmetros de Entrada (JSON Body)
- **`valor_inicial`** *(Decimal > 0)*: Valor nominal em Reais (R$) da obrigação ou parcela a ser reajustada.
- **`data_inicio`** *(date)*: Mês base do contrato/proposta original (formato `YYYY-MM-DD`). Normalizado para o 1º dia do mês.
- **`data_fim`** *(date)*: Mês de vencimento/reajuste monetário desejado (formato `YYYY-MM-DD`). Normalizado para o 1º dia do mês.
- **`sigla`** *(string, opcional, padrão: `INCC-M`)*: Variante do índice estipulada na cláusula contratual (`INCC-M` ou `INCC-DI`).

### 📤 O que é retornado
Objeto `INCCCorrectionResponse` contendo:
- `valor_inicial`: Valor original informado.
- `valor_corrigido`: Valor final atualizado com arredondamento contábil bancário (`ROUND_HALF_UP` em 2 casas decimais).
- `fator_correcao`: Razão matemática exata $\\frac{I_{\\text{final}}}{I_{\\text{inicial}}}$ (8 casas decimais).
- `variacao_acumulada_percentual`: Taxa percentual total de reajuste acumulado no intervalo: $(Fator - 1) \\times 100$.
- `indice_inicial` e `indice_final`: Números-índices de base contínua utilizados no cálculo.

### 💡 Aplicação Prática no Setor AEC
- **Emissão de Boletos na Construção Civil:** Cláusula padrão de compra de imóveis prevê: *"As parcelas vencíveis durante a construção serão corrigidas mensalmente pela variação acumulada do INCC-M"*. Esse endpoint executa essa exata fórmula de forma auditável e instantânea.

### ⚡ Precisão Numérica
Utiliza tipos `Decimal` nativos e encadeamento contínuo em `NUMERIC(28, 6)` no PostgreSQL, prevenindo desvios de arredondamento inerentes ao ponto flutuante IEEE 754.
""",
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
    summary="Raio-X consolidado do mercado da construção civil e dinâmica de momento",
    response_description="Snapshot econômico com taxas atuais de M e DI, spread pontual, acumulados multijanelas e aceleração.",
    responses={
        200: {"description": "Visão geral gerada e retornada com sucesso (via Redis ou PostgreSQL)."},
        404: {"description": "Nenhum dado encontrado no banco de dados. Execute o pipeline de ETL."},
    },
    description="""
### 🎯 O que resolve
Apresenta uma síntese executiva consolidada da inflação da construção civil no mês mais recente, cruzando os índices **INCC-M** e **INCC-DI** em um único payload ultrarrápido, sem necessidade de múltiplas requisições.

### 📤 O que é retornado
Objeto `INCCOverviewResponse` contendo:
- `data_referencia`: Mês de competência mais recente disponível.
- `incc_m` e `incc_di`: Snapshots completos das taxas do mês, YTD, 12M e janelas estendidas de 24M e 36M.
- `spread_mensal_pontos`: Diferença em pontos percentuais entre as duas variantes ($v_{\\text{INCC-M}} - v_{\\text{INCC-DI}}$). Se negativo, indica que o INCC-DI subiu mais que o INCC-M.
- `aceleracao_incc_m`: Análise de momentum inflacionário:
  - `delta_mes_anterior_pontos`: Comparação com o mês imediatamente anterior ($v_t - v_{t-1}$).
  - `delta_ano_anterior_pontos`: Comparação com o mesmo mês do ano anterior ($v_t - v_{t-12}$).
  - `tendencia`: Diagnóstico qualitativo automático (`acelerando`, `desacelerando` ou `estavel`).

### 💡 Aplicação Prática no Setor AEC
- **Comitê de Compras e Suprimentos:** Identificação precoce de aceleração nos custos de insumos da construção para antecipação de compras de aço, concreto e cabeamento elétrico.
- **Relatórios Executivos de Diretoria:** Fornece métricas prontas para o C-level sem requerer cálculos analíticos ad-hoc no frontend.

### ⚡ Estratégia de Cache e Resiliência
- **Chave Redis:** `incc:overview`
- **TTL:** 3.600 segundos (1 hora).
""",
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
    summary="Comparação lado a lado entre INCC-M e INCC-DI ao longo do tempo",
    response_description="Série cronológica unificada com taxas alinhadas, spread e detecção da variante dominante.",
    responses={
        200: {"description": "Série comparativa gerada com sucesso."},
        422: {"description": "Filtro de datas inválido ('data_fim' anterior a 'data_inicio')."},
    },
    description="""
### 🎯 O que resolve
Elimina a necessidade de mesclar manualmente planilhas ou efetuar joins complexos entre tabelas para comparar o **INCC-M** e o **INCC-DI**. Fornece a série temporal unificada com o spread calculado ponto a ponto.

### 📥 Parâmetros de Entrada
- **`data_inicio`** *(date, opcional)*: Data inicial do filtro de observações (YYYY-MM-DD).
- **`data_fim`** *(date, opcional)*: Data final do filtro de observações (YYYY-MM-DD).
- **`skip`** *(int, opcional, padrão: 0)*: Offset para paginação de resultados.
- **`limit`** *(int, opcional, padrão: 100, máx: 1000)*: Tamanho da página.

### 📤 O que é retornado
Objeto `INCCCompareResponse` com lista de itens contendo:
- `data_id`, `ano`, `mes`: Referência temporal.
- `incc_m_variacao_percentual` e `incc_di_variacao_percentual`: Taxas mensais lado a lado.
- `spread_variacao_pontos`: Spread exato em p.p. ($v_{\\text{INCC-M}} - v_{\\text{INCC-DI}}$).
- `variante_maior_taxa`: Indica quem teve maior pressão inflacionária no mês (`INCC-M`, `INCC-DI` ou `EMPATE`).

### 💡 Aplicação Prática no Setor AEC
- **Definição de Cláusulas Contratuais:** Avaliação de qual variante é historicamente mais estável ou mais favorável para construtores ou compradores em diferentes prazos de obra.
- **Auditoria de Divergência Contábil:** Identificação de meses atípicos em que a diferença de apuração entre o dia 20 e o fim do mês gerou grandes distorções de custo.

### ⚡ Estratégia de Cache e Resiliência
- **Chave Redis:** `incc:compare:{dt_start}:{dt_end}:{skip}:{limit}`
- **TTL:** 3.600 segundos (1 hora).
""",
)
def compare_incc_variants(
    data_inicio: Optional[date] = Query(default=None, description="Data inicial para filtro (YYYY-MM-DD)", examples=["2024-01-01"]),
    data_fim: Optional[date] = Query(default=None, description="Data final para filtro (YYYY-MM-DD)", examples=["2024-12-01"]),
    skip: int = Query(default=0, ge=0, description="Offset de paginação", examples=[0]),
    limit: int = Query(default=100, ge=1, le=1000, description="Limite de registros por página", examples=[100]),
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
    summary="Matriz estatística de sazonalidade dos 12 meses do ano civil",
    response_description="Distribuição empírica de médias, desvios e probabilidade de alta para cada mês de Janeiro a Dezembro.",
    responses={
        200: {"description": "Matriz sazonal histórica calculada com sucesso."},
        404: {"description": "Nenhum dado localizado para calcular a sazonalidade da variante."},
        422: {"description": "Sigla informada inválida (deve ser 'INCC-M' ou 'INCC-DI')."},
    },
    description="""
### 🎯 O que resolve
Identifica os padrões sazonais estruturais da construção civil no Brasil ao longo de mais de 80 anos de história (1944 ao presente). Revela os meses do ano com concentração histórica de reajustes salariais (dissídios) e oscilações na demanda por materiais.

### 📥 Parâmetros de Entrada
- **`sigla`** *(string, opcional, padrão: `INCC-M`)*:
  Variante do índice a ser avaliada (`INCC-M` ou `INCC-DI`).

### 📤 O que é retornado
Objeto `INCCSeasonalityResponse` contendo a decomposição para os 12 meses do ano:
- `mes` e `nome_mes`: Mês do calendário (1=Janeiro a 12=Dezembro).
- `total_anos`: Número de anos civis com dados catalogados.
- `media_variacao_percentual` e `mediana_variacao_percentual`: Nível médio e central de inflação daquele mês.
- `desvio_padrao_pontos`: Dispersão histórica das taxas.
- `minima_variacao_percentual` e `maxima_variacao_percentual`: Recordes históricos daquele mês específico.
- `probabilidade_alta_percentual`: Proporção percentual de vezes em que o mês fechou com inflação estritamente positiva.

### 💡 Aplicação Prática no Setor AEC
- **Previsão Orçamentária e Fluxo de Caixa:** Permite ao setor de planejamento antecipar que meses como **Maio e Junho** tradicionalmente concentram picos de reajuste devido aos dissídios sindicais da construção civil na região Sudeste, provisionando caixa com precisão.

### ⚡ Estratégia de Cache e Resiliência
- **Chave Redis:** `incc:seasonality:{sigla}`
- **TTL:** 86.400 segundos (24 horas).
""",
)
def get_seasonality_analysis(
    sigla: str = Query(
        default="INCC-M",
        description="Sigla da série desejada ('INCC-M' ou 'INCC-DI')",
        pattern="^(?i)(INCC-M|INCC-DI)$",
        examples=["INCC-M"],
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
    summary="Resumo estatístico agregado, volatilidade anualizada e recordes históricos",
    response_description="Métricas descritivas globais, desvio padrão, volatilidade e recordes históricos da série.",
    responses={
        200: {"description": "Resumo estatístico calculado com sucesso."},
        404: {"description": "Nenhum dado localizado para calcular as estatísticas da série."},
        422: {"description": "Sigla informada inválida (deve ser 'INCC-M' ou 'INCC-DI')."},
    },
    description="""
### 🎯 O que resolve
Oferece um panorama estatístico abrangente de toda a série histórica, permitindo mensurar a dispersão dos custos da construção, a volatilidade anualizada e os marcos de estresse inflacionário da economia brasileira.

### 📥 Parâmetros de Entrada
- **`sigla`** *(string, opcional, padrão: `INCC-M`)*:
  Variante do índice a ser avaliada (`INCC-M` ou `INCC-DI`).

### 📤 O que é retornado
Objeto `INCCStatsResponse` contendo:
- `total_observacoes`: Quantidade total de observações mensais no banco.
- `data_inicio` e `data_fim`: Intervalo cronológico total coberto.
- `media_mensal_percentual` e `mediana_mensal_percentual`: Medidas de tendência central.
- `desvio_padrao_mensal_pontos`: Desvio padrão amostral mensal.
- `volatilidade_anualizada_percentual`: Volatilidade anualizada calculada pela métrica padrão da econometria $\\sigma \\times \\sqrt{12}$.
- `recorde_alta_percentual` e `recorde_alta_data`: Maior taxa registrada na história e sua data de ocorrência (ex: 78,41% em Março/1990).
- `recorde_baixa_percentual` e `recorde_baixa_data`: Menor taxa registrada na história e sua data de ocorrência.

### 💡 Aplicação Prática no Setor AEC
- **Gestão de Risco e Seguros de Engenharia:** Parametrização de modelos de estresse (stress testing) e cálculo de prêmios de seguro de risco de engenharia e garantias contratuais.
- **Modelagem de Monte Carlo:** Alimentação de premissas estocásticas de volatilidade de custos para estudos de viabilidade econômica de empreendimentos de longo prazo.

### ⚡ Estratégia de Cache e Resiliência
- **Chave Redis:** `incc:stats:{sigla}`
- **TTL:** 86.400 segundos (24 horas).
""",
)
def get_series_statistics(
    sigla: str = Query(
        default="INCC-M",
        description="Sigla da série desejada ('INCC-M' ou 'INCC-DI')",
        pattern="^(?i)(INCC-M|INCC-DI)$",
        examples=["INCC-M"],
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
    summary="Catálogo técnico, fontes primárias e governança metodológica",
    response_description="Catálogo oficial das séries, fontes, metodologia e notas de governança.",
    responses={
        200: {"description": "Metadados e notas de governança retornados com sucesso."},
    },
    description="""
### 🎯 O que resolve
Garante transparência, rastreabilidade e compliance técnico para auditores, desenvolvedores e engenheiros, documentando oficialmente os códigos das séries, metodologias de apuração, órgãos emissores e notas estruturais.

### 📤 O que é retornado
Objeto `INCCMetadataResponse` contendo:
- `series`: Catálogo de cada variante disponível:
  - `sigla`: INCC-M ou INCC-DI.
  - `codigo_bcb`: Código numérico no Sistema Gerenciador de Séries (SGS) do Banco Central (192 para INCC-M, 7456 para INCC-DI).
  - `nome_oficial`: Denominação formal.
  - `fonte_primaria`: FGV IBRE / Banco Central do Brasil.
  - `instituto_responsavel`: Fundação Getulio Vargas (FGV IBRE).
  - `janela_coleta`: Período exato de apuração (21 do mês anterior ao dia 20 vs mês civil).
  - `metodologia`: Resumo metodológico e distribuição de pesos.
- `notas_metodologicas`: Registro de marcos históricos e revisões metodológicas estruturais (como a grande revisão da FGV em Julho de 2023, introduzindo três padrões construtivos).

### 💡 Aplicação Prática no Setor AEC
- **Perícias e Pareceres Técnicos Judiciais:** Embasamento comprobatório de fontes oficiais aceitas pelos Tribunais de Justiça e órgãos fiscalizadores (TCU, Caixa Econômica Federal).

### ⚡ Estratégia de Cache e Resiliência
- **Chave Redis:** `incc:metadata`
- **TTL:** 86.400 segundos (24 horas).
""",
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


