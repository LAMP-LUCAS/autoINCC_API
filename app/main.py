"""Main entry point for the AutoINCC FastAPI application."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.db.session import init_db

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages application startup and shutdown lifecycle events."""
    setup_logging(settings.LOG_LEVEL)
    logger.info("Starting up %s v%s...", settings.APP_NAME, settings.APP_VERSION)

    # Attempt database schema initialization on startup
    try:
        init_db()
        logger.info("Database initialized successfully on startup.")
    except Exception as exc:
        logger.warning(
            "Could not initialize database on startup (database might still be starting): %s",
            exc,
        )

    yield

    logger.info("Shutting down %s...", settings.APP_NAME)


API_DESCRIPTION = """
# 🏗️ AutoINCC API — Documentação Oficial & Guia do Desenvolvedor

Bem-vindo à API oficial do **AutoINCC**, a plataforma aberta de alta performance para extração, padronização, cálculo econômico e distribuição de séries temporais do **Índice Nacional de Custo da Construção (INCC)**.

O AutoINCC é parte integrante do ecossistema de dados abertos para a construção civil (**Mundo AEC**), ao lado do [AutoSINAPI](https://github.com/LAMP-LUCAS/autoSINAPI_API) e do [AutoCUB](https://github.com/LAMP-LUCAS/autoCUB_API).

Acesse o portal central em [mundoaec.com](https://mundoaec.com) para explorar ferramentas interativas, calculadoras, dashboards e documentações completas de todo o ecossistema.


---

## 🏛️ Entendendo o INCC e suas Variantes Oficiais

O INCC é calculado e divulgado pelo **Instituto Brasileiro de Economia da Fundação Getulio Vargas (FGV IBRE)** e publicado oficialmente pelo **Banco Central do Brasil (BCB SGS)**. A plataforma gerencia as duas variantes principais:

| Variante | Código BCB | Janela de Coleta | Aplicação Primária de Mercado |
|---|:---:|---|---|
| **INCC-M** | **192** | Do dia 21 do mês anterior ao dia 20 do mês de referência | **Reajuste de contratos imobiliários na planta**, parcelas com construtoras e medições de obras. |
| **INCC-DI** | **7456** | Do 1º ao último dia do mês civil fechado | Subíndice do IGP-DI, utilizado em **balanços contábeis**, auditorias financeiras e perícias. |

---

## 📐 O Número-Índice Contínuo (Base 100 Móvel)

Diferente de consultas simplórias a taxas isoladas que não permitem cálculos entre períodos não adjacentes, o AutoINCC gera um **número-índice contínuo encadeado** desde 1944:
$$I_t = I_0 \\times \\prod_{k=1}^t (1 + v_k)$$

Isso permite calcular a correção monetária exata entre **quaisquer duas datas da história** através de uma razão direta e auditável:
$$\\text{Fator} = \\frac{I_{\\text{final}}}{I_{\\text{inicial}}}$$
$$\\text{Valor Corrigido} = \\text{Valor Inicial} \\times \\text{Fator}$$

---

## 🚀 Guia Rápido de Endpoints

### 1. Consultas Rápidas e Reajuste Monetário
- **`GET /api/v1/incc/latest`**: Retorna o índice mais recente publicado com variações mensal, YTD e 12 meses.
- **`GET /api/v1/incc/history`**: Extrai séries históricas filtradas por período e variantes com paginação.
- **`POST /api/v1/incc/correction`**: Calculadora de reajuste contratual e correção monetária entre duas datas com precisão bancária.

### 2. Overviews e Inteligência de Mercado (Data-as-a-Service)
- **`GET /api/v1/incc/overview`**: Raio-X do mercado no último mês publicado: taxas de M e DI, spread pontual, acumulados multijanelas (24M, 36M) e diagnóstico de aceleração/momentum.
- **`GET /api/v1/incc/compare`**: Série temporal unificada alinhando INCC-M e INCC-DI lado a lado com cálculo de spread e detecção de dominância.
- **`GET /api/v1/incc/analytics/seasonality`**: Matriz de sazonalidade dos 12 meses do ano civil calculada sobre todo o histórico (médias, medianas e probabilidade de inflação positiva).
- **`GET /api/v1/incc/analytics/stats`**: Resumo estatístico agregado da série: volatilidade anualizada ($\\sigma \\times \\sqrt{12}$) e recordes históricos de alta e baixa.
- **`GET /api/v1/incc/metadata`**: Catálogo técnico, notas metodológicas e janelas de apuração.

### 3. Administração e Ingestão de Dados
- **`POST /api/v1/etl/trigger`**: Disparo sob demanda do pipeline assíncrono via Celery Worker (protegido por `X-API-Key`).

---

## ⚡ Cache L2 no Redis & Performance
- **Leituras em < 3ms:** Todas as rotas de consulta analítica e séries são mantidas em cache Redis L2 com TTL otimizado.
- **Invalidação Orientada a Eventos:** Assim que uma nova ingestão é concluída pelo Celery Worker, as chaves sob o prefixo `incc:*` são invalidadas automaticamente.
- **Tolerância a Falhas:** Se o Redis estiver indisponível, a API degrada elegantemente para o PostgreSQL sem impactar os clientes.
"""

TAGS_METADATA = [
    {
        "name": "INCC",
        "description": "Consultas analíticas, séries temporais históricas, comparativos e ferramenta de reajuste monetário contratual.",
    },
    {
        "name": "ETL",
        "description": "Disparo manual e orquestração assíncrona do pipeline de ingestão e transformação via Celery Worker.",
    },
    {
        "name": "Health",
        "description": "Sondas de monitoramento de integridade e liveness probe para orquestração de containers Docker.",
    },
    {
        "name": "Root",
        "description": "Identificação básica da API e versão do serviço.",
    },
]

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    summary="API RESTful de Alta Performance para Índices de Custo da Construção Civil (INCC)",
    description=API_DESCRIPTION,
    openapi_tags=TAGS_METADATA,
    contact={
        "name": "Mundo AEC / Equipe AutoINCC",
        "url": "https://mundoaec.com",
        "email": "contato@mundoaec.com",
    },
    license_info={
        "name": "GNU General Public License v3.0 (GPLv3)",
        "url": "https://www.gnu.org/licenses/gpl-3.0",
    },
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Configure CORS securely for web applications, dashboards, and integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/",
    tags=["Root"],
    summary="Root service status",
)
def root() -> Dict[str, str]:
    """Returns basic service identity and version."""
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "status": "online",
        "docs": "/docs",
    }


@app.get(
    "/health",
    tags=["Health"],
    summary="Health check endpoint",
    status_code=status.HTTP_200_OK,
)
def health_check() -> Dict[str, str]:
    """Service health verification probe for container orchestration."""
    return {"status": "healthy"}


# Mount v1 routes
app.include_router(api_v1_router, prefix=settings.API_V1_STR)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
