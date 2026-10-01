# Manual de manutenção — AutoINCC_API

> API do **INCC** (Índice Nacional de Custo da Construção) + o servidor MCP
> embutido (`autoincc_mcp/`). Série oficial **FGV** (INCC-M mensal, INCC-DI
> acumulado). O [README](../README.md) diz como usar; este diz como manter.

---

## 1. A doutrina

Mesma doutrina do ecossistema (AutoCUB / AutoSINAPI):

> **Só há sinal com FATO. Nunca desacreditar o valor oficial. Falhar alto e
> nomeado** (ADR 010). **Número é JSON number** (ADR 009).

Para o INCC isso tem um peso extra: os índices são **publicados pela FGV**, com
**escala oficial** (base 100 = ago/1994). Um índice lido na escala errada é
número plausível e errado — foi o achado mais grave da campanha aqui.

---

## 2. Mapa do código

```
app/
├── api/v1/incc.py    todas as rotas (latest, history, correction, analytics…)
├── schemas/
│   ├── incc.py       resposta de correção/registro — `Num` (Decimal→float)
│   └── analytics.py  resposta de agregados (overview, compare, stats…)
├── core/
│   ├── config.py     env-driven
│   ├── cache.py      cache Redis dos analytics
│   └── numerico.py   ★ `Num`: Decimal no cálculo, float na resposta (ADR 009)
├── services/         regras de agregação (analytics_service)
├── etl/              coleta da FGV
└── db/models.py      colunas NUMERIC (o Decimal vive aqui)

autoincc_mcp/         servidor MCP embutido (8 tools) — ver o próprio README
tests/                pytest (rodar no container / com Postgres)
```

**Onde mexer:** rota → `api/v1/incc.py`; forma do JSON → `schemas/`;
agregações → `services/`; coleta → `etl/`; série/fator → `core/numerico.py`
(tipo, não lógica).

---

## 3. O contrato de resposta (invariantes)

| Estado | HTTP | Corpo |
|---|---|---|
| com dado | 200 | a resposta (números como `number`) |
| **sem dado** | 200 | envelope explícito, nunca lista vazia crua |
| erro | 4xx/5xx | `detail` nomeado (ex.: `data_fim cannot be prior to data_inicio`) + `correlation_id` |

Invariantes com claim de gate:

1. **Número é `number`**, nunca string (ADR 009 — `Num` em todos os schemas de
   resposta; banco continua `NUMERIC`).
2. `data_fim < data_inicio` **rejeitado** com mensagem clara (não "inverte
   silenciosamente").
3. `metadata.inicio_serie` é **derivado dos dados reais**, não do rótulo do
   arquivo (§4.3).
4. **Janela explícita** nas agregações: `stats` devolve `padrao`, `ano_inicio`,
   `ano_fim` (padrão 120 meses) — o agente sabe o que está olhando (§4.4).
5. Índice sempre **na escala oficial** (§4.1).
6. Recomendações e limites no `description` da rota (o agente lê).

---

## 4. Evolução da campanha (o que mudou)

| § | Defeito | Correção |
|---|---|---|
| **4.1** | INCC-M **vazava/leitura na escala errada** (o oficial é base 100 = ago/1994) | ETL e leitura na **escala oficial FGV**; reprocesso com backup. Índice agora na faixa real |
| **4.2** | comparativo/spray comparava séries de **datas diferentes** | spread só com séries **na mesma data de referência** |
| **4.3** | `metadata` dizia um `inicio_serie` que o dado não tinha | `inicio_serie` **derivado** + `observacoes_disponiveis` — metadata fiel |
| **4.4** | `stats` sem janela: janela fixa e opaca | **janela explícita** (`ano_inicio`/`ano_fim`, default 120m) **no payload** |
| **4.5** | agregados vazavam índice fora da faixa plausível | claim vigia que **não vaza** (§4.1) |
| **2.1** | agente sem referência legível | **MCP resources** |
| **2.2** | tools sem descrição | guard: **nenhuma** descrição vazia |
| **X-01** | todo número vinha como **string** (`"250000.00"`) | `Num` em ~40 campos: **number** no JSON, `Decimal` no cálculo (ADR 009) |

---

## 5. Como manter (receitas)

### 5.1 Adicionar rota / agregação
1. Rota em `api/v1/incc.py` com `response_model` em `schemas/analytics.py`
   (ou `incc.py`).
2. **Numérico → `Num`**, nunca `Decimal` cru (ADR 009).
3. Se é agregação com janela, exponha a janela no payload (padrão do `stats`).
4. Se a resposta é "série", derive `metadata` **dos dados** (padrão §4.3).
5. Teste em `tests/`.

### 5.2 Mexer na ETL
Escrita/valor: colunas `NUMERIC` em `app/db/models.py`. A coleta FGV fica em
`app/etl/`. Reprocesso = **backup antes** (regra do projeto).

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
PYTHONPATH=. python3 -m pytest tests/ autoincc_mcp/tests/ -q
```

---

## 6. Armadilhas conhecidas

| Armadilha | O que fazer |
|---|---|
| **`Decimal` em schema** | vira string no JSON. Use `Num` (`app/core/numerico.py`) — ADR 009 |
| **Escala do índice** | oficial = base 100 = **ago/1994**. Índice na escala errada é plausível-e-errado (§4.1) |
| **`metadata` de arquivo** | o rótulo do PDF não é a série real; derive dos dados (§4.3) |
| **Janela oculta** | agregação sem janela explícita é opaca para o agente — exponha (§4.4) |
| **Data invertida** | `data_fim < data_inicio` se rejeita com mensagem, não se "corrige" |
| **ETL = escrita em `NUMERIC`** | banco guarda Decimal; só a resposta vira float |
| 🔴 **`API_KEY` do trigger de ETL tem default hardcoded** | `app/core/config.py` define um valor de dev como **padrão** (o mesmo aparece no `docker-compose.yml` e no README). Sem a env var `API_KEY`, o serviço sobe com uma chave conhecida publicamente e o `POST /api/v1/etl/trigger` fica aberto. **Não propague**: troque o default por vazio/erro (falhar alto, ADR 010) e rotacione a chave. Ver o registro em §6.1 |

### 6.1 🔴 Pendência de segurança (pré-existente, não introduzido aqui)

O endpoint administrativo de disparo do ETL (`POST /api/v1/etl/trigger`) é
protegido por `API_KEY`, cujo **valor padrão está no código**
(`app/core/config.py`) e é replicado no `docker-compose.yml` e no `README.md`.
Enquanto o default existir, qualquer instalação que não defina a variável de
ambiente sobe com uma credencial pública — o endpoint aceita disparo de ETL sem
autenticação effectively.

**Recomendação** (decisão de segurança, precisa de execução própria):

1. `API_KEY` deixa de ter default — ausência = serviço não sobe (fail-loud,
   ADR 010) ou o trigger fica desabilitado explicitamente;
2. rotacionar o valor atual (está em histórico Git);
3. `.env.example` só com placeholder, nunca valor.

> Registrado aqui porque um maintainer que leia `config.py` pode reproduzir o
> default. **Não citei o valor** de propósito.

---

## 7. Referências

- **ADR 009** (tipagem) e **ADR 010** (fail-loud): moram em
  [autosinapi_api/docs/adrs/](../../autosinapi_api/docs/adrs/) e valem para todo o
  ecossistema.
- Story da campanha: [`docs/PLAN-auditoria-mcp-p0.md`](PLAN-auditoria-mcp-p0.md)
- Manual equivalente do AutoCUB (mesma doutrina, com o caso AM):
  [autocub_api/docs/MANUAL_DE_MANUTENCAO.md](../../autocub_api/docs/MANUAL_DE_MANUTENCAO.md)
- Manual do SINAPI: [autosinapi_api/docs/MANUAL_DE_MANUTENCAO.md](../../autosinapi_api/docs/MANUAL_DE_MANUTENCAO.md)