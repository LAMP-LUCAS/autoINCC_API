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

- [ ] **RED:** teste de regressão: `process_series` de amostra M com variações
      oficiais deve produzir `numero_indice` em faixa plausível (ex.: 50–5000 para
      base 100 com ~82 anos — calibrar com a série real); hoje falha em 1e15.
- [ ] **Fix:** corrigir o fator/base na origem (processor ou caller).
- [ ] **REENG:** asserção de sanidade no loader (`app/etl/loader.py`):
      rejeitar/faillar carga com `numero_indice` fora de faixa — nunca persistir
      silenciosamente.
- [ ] **Reprocesso da série M:** backup do `fato_incc` antes; reprocessar;
      conferir razões mês a mês (1,041586 do `incc_correction` como referência);
      verificar `incc_latest/history/overview` e o campo `indice_inicial/final`
      de `incc_correction` após o fix.
- [ ] P1 relacionado (adiado com o P1): §4.2 spread de meses diferentes;
      §4.3 `inicio_serie` do metadata; §4.4 `incc_stats` sem janela; §4.5 cai junto.

## Também registrado

- **Positivo a preservar:** `incc_correction` (razões) bate com produto independente
  (Δ=0,000002); `incc_metadata` é boa doc metodológica; série íntegra 990 obs.
- Commits locais não pushados (`9286ad9`, `b12fb55`) são trabalho pré-existente —
  preservados; push conjunto apenas depois (decisão 2026-09-29).

## Regras

- TDD (RED antes do fix), DDD do app (`app/etl` = camada de domínio de ingestão).
- Nunca imprimir credencial; backup obrigatório antes de reprocessar (decisão 2026-09-29).
