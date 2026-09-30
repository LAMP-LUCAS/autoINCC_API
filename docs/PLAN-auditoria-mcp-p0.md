# PLAN — Auditoria MCP de Custo (P0) — AutoINCC

> Origem: auditoria externa 2026-09-29 · Plano mestre na casa:
> `SistemaServerLight/docs/plans/PLAN-auditoria-mcp-custo-p0.md`.
> Status: **Em andamento** (2026-09-29).

## Escopo deste repositório (P0)

### §4.1 — `numero_indice` do INCC-M corrompido (fator ≈ 1e15, mantissa correta)

**Evidência da auditoria (PROVADO):**

| Mês | Retornado | Mantissa real |
|---|---|---|
| 2026-01 | `1040218844486427400.000000` | 1040,2188444864274 |
| 2026-07 | `1083477441865997000.000000` | 1083,477441865997 |

Razões entre meses corretas (1,041565 idêntico por ambas as contas) → **só a
escala absoluta está errada**; série irmã INCC-DI limpa (`119.115357`) → defeito
específico da cadeia M. `incc_correction` (razões) está correto e permanece a
superfície segura.

**Causa-raiz provável (leitura):** `app/etl/processor.py` L118-119 —
`numero_indice = base_index * (factor.cumprod() * initial_cumulative_factor)`.
Fator constante ≈1e15 aplicado na construção da cadeia M (`initial_cumulative_factor`
ou base passada pelo orquestrador do ETL) — a confirmar no RED localizando quem
chama `process_series` para `tipo_id=1`.

**Plano:**

- [x] **RED:** teste de regressão: `process_series` de amostra M com variações
      oficiais deve produzir `numero_indice` em faixa plausível (ex.: 50–5000 para
      base 100 com ~82 anos — calibrar com a série real); hoje falha em 1e15.
      → `tests/test_numero_indice_oficial.py` (fixture BCB SGS 192 completo,
      991 obs) — RED por `TypeError(base_date)` + faixa; GREEN após fix.
- [x] **Fix:** corrigir o fator/base na origem (processor ou caller).
      → Causa-raiz refinada por evidência (a hipótese "fator 1e15 no código"
      foi **refutada**: `numero_indice` reproduz a cadeia BCB fielmente, razão
      1,0). O defeito é a **escolha da base**: cadeia desde fev/1944 (base 100)
      gera ~1e18; a série oficial FGV (xlsx Sinduscon-PR) tem **base 100 =
      01/08/1994**. Fix: `calculate_metrics(base_date=...)` rebasa a cadeia na
      data-base oficial (`SERIES_MAP[192]`), mantendo razões invariante
      (`incc_correction` intacto). `base_date` ausente → `ValueError` (nunca
      escala divergente silenciosa). Arredondamento de `numero_indice` 6→15
      casas (obs. pré-base < 1e-6 não podem ser zeradas).
- [x] **REENG:** asserção de sanidade no loader (`app/etl/loader.py`):
      rejeitar/faillar carga com `numero_indice` fora de faixa — nunca persistir
      silenciosamente. → guard `(0, 100_000]` antes do upsert +
      `tests/test_loader_guard.py`.
- [x] **Reprocesso da série M:** backup do `fato_incc` antes; reprocessar;
      conferir razões mês a mês (1,041586 do `incc_correction` como referência);
      verificar `incc_history/overview` e o campo `indice_inicial/final`
      de `incc_correction` após o fix.
      → Backup: `/mnt/ssd_serv_220G/backups/autoincc/fato_incc_pre_reprocesso_20260929.sql`
      (1056 linhas, contém o dado pré-fix); migração de coluna
      `fato_incc.numero_indice`: `NUMERIC(28,6)` → `NUMERIC(38,15)` (15 casas
      preservam razões pré-1990; 23 dígitos inteiros cabem no legado);
      reprocesso série 192 (991/991, 0 erros); verificação: âncora
      1994-08 = 100.000000000000000 exato, jul/2026 = 1287.83 (oficial FGV
      1283.035, +0,37%), razão 07/01 = **1.041586 idêntica**, 0 obs fora de
      `(0, 100_000]`, DI intacta; gate da casa: **§4.1 OK** (7 obs, fora: 0).
- [x] **P1 §4.2 spread de meses iguais** → GREEN incidental pós-reprocesso §4.1
      (M e DI ambas em 2026-08, spread=-0,19; gate OK).
- [x] **P1 §4.3 `inicio_serie` do metadata** (2026-09-30) — RED
      `tests/test_metadata_inicio_serie.py`: INCC-DI declarava `1944` por
      CONSTANTE sem dado em 1944 (carga parcial `data_inicial=2024-01-01`;
      o oficial do SGS 7456 começa 01/09/**1994**). Fix: `inicio_serie`
      derivado da primeira observação armazenada + `observacoes_disponiveis`
      (recomendação da auditoria; nota: 7456 tem 306 obs desde 01/09/1994,
      banco tem só 32 desde 2024-01 — carga total fica p/ P2, a carga parcial
      agora é declarada). Gate: **§4.3 OK** (2 séries conferidas).
- [ ] P1/P2 adiados: §4.4 `incc_stats` sem janela; §4.5 cai junto (fora do
      gate P1 aprovado; planejar no próximo ciclo).

## Também registrado

- **Positivo a preservar:** `incc_correction` (razões) bate com produto independente
  (Δ=0,000002); `incc_metadata` é boa doc metodológica; série íntegra 990 obs.
- Commits locais não pushados (`9286ad9`, `b12fb55`) são trabalho pré-existente —
  preservados; push conjunto apenas depois (decisão 2026-09-29).

## Regras

- TDD (RED antes do fix), DDD do app (`app/etl` = camada de domínio de ingestão).
- Nunca imprimir credencial; backup obrigatório antes de reprocessar (decisão 2026-09-29).
