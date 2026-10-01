# Manual de manutenção — autoincc_mcp

> Servidor **MCP** (Model Context Protocol) do AutoINCC: 8 tools + 2 resources.
> É a camada que o **agente** consome (via `mcp-autoincc.mundoaec.com/sse`).
> Mora **dentro** do repo da API — a separação é de código, não de repositório.

---

## 1. A doutrina

Mesma doutrina do ecossistema (ver [manual do AutoCUB](../../../autocub_api/docs/MANUAL_DE_MANUTENCAO.md),
que a provou com o caso AM):

> **Só há sinal com FATO. Nunca desacreditar o valor oficial. Falhar alto e
> nomeado** (ADR 010). **Número é JSON number** (ADR 009).

Para o MCP do INCC isso significa: a tool é a **última fronteira de
confiança**. Índice na escala errada, ou como string, chega bonito ao agente e
quebra o orçamento.

---

## 2. Mapa do código

```
autoincc_mcp/src/autoincc_mcp/
├── server.py        registra as 8 tools (nome + descrição) e os 2 resources
├── tools/
│   ├── tier_1.py    3 tools de catálogo (latest, history, metadata)
│   └── tier_2.py    5 tools de análise (correction, overview, compare,
│                    seasonality, stats)
├── client.py        HTTP + erros nomeados + `correlation_id`
├── resolver.py      path da API → rótulo legível
├── auth.py          credencial POR REQUEST
├── cache.py         cache por identidade
├── config.py        env-driven
└── resources.py     resources legíveis (referência INCC para o agente)
```

**Camadas:** `server.py` (registro) → `tools/` (regra da tool) → `client.py`
(transporte + erro) → API. A tool **não interpreta** o índice: ela repassa
com a tipagem e o rótulo certainos.

---

## 3. O contrato de resposta (invariantes)

| Estado | `isError` | Corpo |
|---|---|---|
| com dado | `false` | a resposta, **números como `number`** |
| sem dado | `false` | envelope explícito, nunca vazio cru |
| erro | `true` | `<código>: <causa> [correlation_id=…]` |

Invariantes com claim de gate:

1. **Número é `number`** (ADR 009) — `incc_correction` devolve
   `valor_inicial`, `fator_correcao`, `indice_inicial` como número.
2. **Datas string ISO**; `data_fim < data_inicio` **rejeitado** com mensagem
   clara (não invertido).
3. **Toda descrição de tool é não-vazia e útil** (claim `§2.2`; 8/8 hoje) — e
   declara que números chegam como `number` (para o agente não parsear texto).
4. **Resources legíveis** (claim `§2.1`) — é como o agente descobre a série sem
   gastar tool.
5. Erro tem `correlation_id`.
6. `stats` devolve a **janela usada** (`padrao`, `ano_inicio`, `ano_fim`) — o
   agente sabe o recorte (claim `§4.4`).

---

## 4. Evolução da campanha (o que mudou aqui)

| § | Mudança (neste repo ou no contrato com a API) |
|---|---|
| **2.1** | **2 resources** de referência INCC, legíveis pelo agente |
| **2.2** | guard permanente: **nenhuma** tool sem descrição |
| **4.4** | `incc_stats` passou a aceitar/ecoar a **janela** (o MCP refletiu o contrato novo) |
| **X-01** | descrição de `incc_correction` **declara a tipagem** (`number`), porque o consumidor precisa saber antes de somar; junto veio a migração `Decimal`→`float` na resposta da API |

> **Padrão:** o MCP é onde se **declara** ao agente o que ele vai receber
> (formato, limites, tipagem). A migração do dado é da API; a **clareza** do
> contrato é do MCP.

---

## 5. Como manter (receitas)

### 5.1 Adicionar uma tool
1. Função `async def incc_*` em `tools/tier_1.py` (catálogo) ou `tier_2.py`
   (análise), com **docstring que serve de descrição**.
2. Documente na descrição: **formato, limites, tipagem e o que "sem dado"
   significa**.
3. `api_key = resolve_api_key(ctx)`; cache por identidade.
4. Registre em `server.py` (`TOOLS`).
5. Teste em `autoincc_mcp/tests/test_tools_tier*.py`.

### 5.2 Declaração de tipagem
Se a tool devolve número, a descrição diz: **"todo valor numérico é JSON
`number`; datas são string ISO"** (ADR 009). O agente não deve supor string.

### 5.3 Rodar a verificação (gate)
```bash
for r in autosinapi_redis autocub_redis autoincc_redis; do
  docker exec $r redis-cli -n 0 FLUSHDB
done
REDIS_CONTAINER=api-gateway-redis bash stacks/autosinapi/kong/scripts/flush_cache.sh

python3 automation/scripts/verify_mcp_audit_claims.py   # exit 0 = verde
```

### 5.4 Rodar os testes
```bash
PYTHONPATH=. python3 -m pytest autoincc_mcp/tests/ -q
```

---

## 6. Armadilhas conhecidas

| Armadilha | O que fazer |
|---|---|
| **Número como string** | se a API voltar `Decimal`, virou `"250000.00"` — use `Num` na API (ADR 009) e declare na descrição |
| **Escala do índice** | o INCC-M oficial é base 100 = **ago/1994**; índice na escala errada é plausível-e-errado |
| **Data invertida** | `data_fim < data_inicio` se **rejeita** com mensagem; não "corrige" nem embala |
| **Credencial/cache** | por request e por identidade; nada global |
| **Janela oculta** | agregação sem janela explícita é opaca — exponha (padrão do `stats`) |

---

## 7. Referências

- **API (mesmo repo):** [`docs/MANUAL_DE_MANUTENCAO.md`](../../docs/MANUAL_DE_MANUTENCAO.md)
- Story da campanha: [`docs/PLAN-auditoria-mcp-p0.md`](../../docs/PLAN-auditoria-mcp-p0.md)
- **ADR 009 / 010:**
  [autosinapi_api/docs/adrs/](../../../autosinapi_api/docs/adrs/)
- Doutrina equivalente no CUB:
  [autocub_api/docs/MANUAL_DE_MANUTENCAO.md](../../../autocub_api/docs/MANUAL_DE_MANUTENCAO.md)