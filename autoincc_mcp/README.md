# AutoINCC MCP Server

Adapter MCP para índices INCC e correção monetária. O transporte público usa
Streamable HTTP em `/sse` e SSE legado; o callback é `/messages/`.

## 🛠️ Mantendo o Projeto

Vai **modificar** este MCP? Comece pelo **[📘 Manual de Manutenção](docs/MANUAL_DE_MANUTENCAO.md)** —
doutrina, contrato de resposta (inclusive a tipagem `number` que a descrição
declara), a evolução da auditoria e armadilhas (escala oficial, data invertida).

- **[Manual do MCP](docs/MANUAL_DE_MANUTENCAO.md)** · [Manual da API](../docs/MANUAL_DE_MANUTENCAO.md)

## Credencial

Em HTTP, a `X-API-KEY` é lida do contexto da requisição pelo FastMCP e
repassada somente em memória ao cliente interno. A credencial não é campo de
tool, não aparece no schema e o cache é particionado por digest. Em stdio, a
chamada local pode usar uma chave explícita; chamadas HTTP sem header falham
fechadas.

O upstream padrão é o gateway autorizado (`AUTOINCC_BASE_URL`). O servidor não
deve apontar para um upstream interno para contornar tier ou quota.

## Testes

```bash
PYTHONPATH=src pytest -q
```
