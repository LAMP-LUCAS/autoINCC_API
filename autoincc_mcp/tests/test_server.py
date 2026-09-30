import json
from unittest.mock import AsyncMock, patch

import httpx
from starlette.routing import Match

from autoincc_mcp.server import create_http_app, create_server, main


async def test_registration():
    server = create_server()
    tools = await server.list_tools()
    names = {tool.name for tool in tools}
    assert names == {
        "incc_latest",
        "incc_history",
        "incc_correction",
        "incc_overview",
        "incc_compare",
        "incc_seasonality",
        "incc_stats",
        "incc_metadata",
    }
    assert len(tools) == 8
    for tool in tools:
        assert "api_key" not in tool.inputSchema.get("properties", {})
        assert "ctx" not in tool.inputSchema.get("properties", {})
    assert server.settings.port == 8080


async def test_all_tools_have_one_liner_descriptions():
    """§2.2 (auditoria MCP de custo): guard — nenhuma tool com descrição vazia.

    A auditoria encontrou 19 descrições `""` no AutoSINAPI (o campo que o
    agente lê na descoberta). Este guard impede regressão nesta superfície:
    toda tool precisa de um one-liner legível (>= 10 chars úteis).
    """
    server = create_server()
    for tool in await server.list_tools():
        assert tool.description and tool.description.strip(), tool.name
        assert len(tool.description.strip()) >= 10, tool.name


async def test_exposes_resources_for_agents():
    """§2.1 (auditoria MCP de custo): o servidor precisa expor MCP resources
    legíveis por agente — a auditoria encontrou `resources: []` nos 3
    servidores (sem schema, tabela de códigos nem referência metodológica).

    Contrato: >=1 resource com name + descrição sintética (>=10 chars),
    mimeType declarado e conteúdo legível (>=200 chars) no resources/read.
    """
    server = create_server()
    resources = await server.list_resources()
    assert resources, "§2.1: nenhum resource exposto"
    for r in resources:
        assert r.name and r.description and len(r.description.strip()) >= 10, r.uri
        assert r.mimeType, r.uri
    contents = await server.read_resource(resources[0].uri)
    text = "".join(
        c.content.decode() if isinstance(c.content, bytes) else c.content
        for c in contents)
    assert len(text) >= 200, "§2.1: conteúdo do resource muito curto"


def test_both_transports_route():
    app = create_http_app(create_server())
    for method in ("GET", "POST", "DELETE"):
        scope = {"type": "http", "path": "/sse", "root_path": "", "method": method}
        assert any(route.matches(scope)[0] == Match.FULL for route in app.routes)
    assert any(route.path == "/messages" for route in app.routes)


async def test_streamable_handshake_and_discovery():
    server = create_server()
    app = create_http_app(server)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client,
    ):
        headers = {"Accept": "application/json, text/event-stream"}
        response = await client.post(
            "/sse",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "unit-test", "version": "1"},
                },
            },
        )
        assert response.status_code == 200
        headers["Mcp-Session-Id"] = response.headers["mcp-session-id"]
        headers["MCP-Protocol-Version"] = "2025-03-26"
        response = await client.post(
            "/sse", headers=headers, json={"jsonrpc": "2.0", "method": "notifications/initialized"}
        )
        assert response.status_code == 202
        response = await client.post(
            "/sse", headers=headers, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
        )
        data = next(line[6:] for line in response.text.splitlines() if line.startswith("data: "))
        assert len(json.loads(data)["result"]["tools"]) == 8
        assert (await client.get("/health")).json()["status"] == "ok"


async def test_lifespan_closes_resources():
    from autoincc_mcp.server import lifespan

    with patch("autoincc_mcp.server.tier_1.close_resources", new_callable=AsyncMock) as close:
        async with lifespan(create_server()):
            close.assert_not_awaited()
        close.assert_awaited_once()


def test_main_http():
    with patch("autoincc_mcp.server.uvicorn.run") as run:
        main()
    assert run.call_args.kwargs["port"] == 8080


def test_main_stdio(monkeypatch):
    monkeypatch.setenv("AUTOINCC_MCP_TRANSPORT", "stdio")
    with patch("autoincc_mcp.server.create_server") as create:
        main()
    create.return_value.run.assert_called_once_with(transport="stdio")
