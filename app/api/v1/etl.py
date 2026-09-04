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
    summary="Disparar pipeline assíncrono de ETL via Celery Worker",
    response_description="Confirmação de recebimento e agendamento da extração com ID da tarefa.",
    responses={
        202: {"description": "Tarefa de ETL aceita e enfileirada com sucesso (via Celery/Redis ou BackgroundTasks)."},
        403: {"description": "Acesso não autorizado: token de API ausente ou inválido no cabeçalho 'X-API-Key'."},
        422: {"description": "Erro de validação nos dados fornecidos na requisição."},
    },
    description="""
### 🎯 O que resolve
Permite que operadores de sistema, rotinas automatizadas (cron jobs / agendadores externos) ou pipelines CI/CD disparem sob demanda a sincronização do banco de dados com as fontes oficiais do Banco Central do Brasil (SGS) e FGV.

### 🔐 Autenticação e Segurança
- **Cabeçalho Obrigatório:** `X-API-Key: {seu_token_secreto}`
- Rejeita com `403 Forbidden` qualquer requisição que não apresente a chave configurada no ambiente (`API_KEY`).

### 📥 Parâmetros de Entrada (JSON Body opcional)
- **`series_codes`** *(list[int], opcional)*:
  Lista de códigos numéricos de séries BCB SGS. Se omitido, processa todas as cadastradas (`[192, 7456]`).
- **`data_inicial`** *(date, opcional)*:
  Data inicial do recorte (formato `YYYY-MM-DD`). Se omitido, busca o histórico completo.
- **`data_final`** *(date, opcional)*:
  Data final do recorte (formato `YYYY-MM-DD`).

### 📤 O que é retornado
Objeto `ETLTriggerResponse` contendo:
- `status`: Sempre `"accepted"` (código HTTP 202).
- `task_id`: Identificador UUIDv4 único da tarefa no Celery ou worker local.
- `triggered_at`: Carimbo de data e hora UTC do agendamento.
- `series`: Códigos de séries submetidos ao processamento.

### ⚙️ Resiliência e Fallback Transparente
1. **Fila Primária:** A tarefa é enviada ao broker Redis para execução assíncrona desacoplada no `autoincc_celery_worker`.
2. **Fallback Automático:** Caso o Redis ou Celery estejam temporariamente inalcançáveis, a API redireciona o processamento para as `BackgroundTasks` nativas do FastAPI, garantindo que a extração ocorra sem falhar a chamada do cliente.
3. **Pacing Ético:** Cada chamada aos servidores governamentais aplica jitter estocástico aleatório ($1,5\\text{s} - 3,0\\text{s}$) e headers de browser para evitar bloqueios ou sobrecarga nos órgãos emissores.
4. **Invalidação de Cache:** Ao concluir com sucesso, o pipeline invalida automaticamente todas as chaves do Redis sob o padrão `incc:*`.
""",
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
