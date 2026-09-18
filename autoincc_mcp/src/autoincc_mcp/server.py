import logging
import sys
from contextlib import asynccontextmanager

import structlog
import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from autoincc_mcp.config import get_config
from autoincc_mcp.tools import tier_1, tier_2

TOOLS = (
    (tier_1.incc_latest, "Índice INCC recente, fonte, taxas e referência temporal."),
    (tier_1.incc_history, "Série histórica INCC paginada por datas e variante."),
    (tier_2.incc_correction, "Correção monetária em reais via REST, sem persistência."),
    (tier_2.incc_overview, "Panorama consolidado das variantes INCC-M e INCC-DI."),
    (tier_2.incc_compare, "Comparação histórica paginada de INCC-M e INCC-DI."),
    (tier_2.incc_seasonality, "Sazonalidade histórica da variante INCC."),
    (tier_2.incc_stats, "Estatísticas agregadas da série INCC."),
    (tier_1.incc_metadata, "Catálogo de séries, fontes e notas metodológicas INCC."),
)


def setup_logging() -> None:
    structlog.configure(
        processors=[structlog.stdlib.add_log_level, structlog.dev.ConsoleRenderer()],
        logger_factory=structlog.stdlib.LoggerFactory(),
    )
    logging.basicConfig(stream=sys.stderr, level=get_config().log_level, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(server: FastMCP):
    try:
        yield {}
    finally:
        await tier_1.close_resources()


def create_server() -> FastMCP:
    config = get_config()
    server = FastMCP(
        "AutoINCC",
        host=config.mcp_host,
        port=config.mcp_port,
        log_level=config.log_level,
        lifespan=lifespan,
    )
    for function, description in TOOLS:
        server.tool(name=function.__name__, description=description)(function)
    return server


async def health(request):
    return JSONResponse({"status": "ok", "service": "autoincc-mcp"})


def create_http_app(server: FastMCP) -> Starlette:
    server.settings.streamable_http_path = "/sse"
    sse_routes = list(server.sse_app().routes)
    app = server.streamable_http_app()
    for route in reversed(sse_routes):
        app.routes.insert(0, route)
    app.routes.append(Route("/health", health, methods=["GET"]))
    return app


def main() -> None:
    setup_logging()
    config = get_config()
    server = create_server()
    if config.mcp_transport == "streamable-http":
        uvicorn.run(
            create_http_app(server),
            host=config.mcp_host,
            port=config.mcp_port,
            log_level=config.log_level.lower(),
        )
    else:
        server.run(transport=config.mcp_transport)


if __name__ == "__main__":
    main()
