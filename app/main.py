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


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "**AutoINCC API**: Sistema open-source para automação da extração, "
        "transformação, cálculo econômico e disponibilização do Índice Nacional "
        "de Custo da Construção (INCC) via API do Banco Central (SGS) e FGV."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Configure CORS for frontend and dashboard integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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
