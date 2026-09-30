"""MCP resources do AutoINCC — §2.1 da auditoria MCP de custo.

A auditoria encontrou `list_mcp_resources() → {"resources": []}` nos três
servidores: nenhum schema legível por agente, tabela de códigos, referência
metodológica ou exemplo. Aqui o material é sintetizado de fontes já
existentes (nada é inventado):

- catálogo e notas metodológicas oficiais da plataforma — payload de
  `GET /api/v1/incc/metadata` (capturado ao vivo 2026-09-30);
- assinaturas/defaults das tools (`tools/tier_1.py`, `tools/tier_2.py`);
- contrato de janela de `incc_stats` (auditoria §4.4).
"""

_SERIES = """\
# AutoINCC — séries e metodologia (§2.1)

Catálogo oficial da plataforma (payload de `incc_metadata`).

| Série | Nome oficial | BCB | Janela de coleta | Início | Observações |
|---|---|---|---|---|---|
| INCC-M | Índice Nacional de Custo da Construção - Mercado | 192 | dia 21 do mês anterior → dia 20 do mês de referência | 1944 | 991 |
| INCC-DI | Índice Nacional de Custo da Construção - Disponibilidade Interna | 7456 | primeiro → último dia do mês civil de referência | 2024 | 32 |

- **Fonte:** FGV IBRE / Banco Central do Brasil (SGS). Periodicidade mensal.
- **INCC-M:** custos de construção habitacional em 7 capitais (SP, RJ, BH,
  POA, Salvador, Recife, Brasília) — materiais, serviços e mão de obra;
  uso típico: reajuste de contratos na planta.
- **INCC-DI:** subíndice do IGP-DI; mês calendário fechado; uso típico:
  balanços corporativos, análises contábeis e liquidações contratuais.

## Notas metodológicas

1. **Revisão metodológica (jul/2023):** o FGV IBRE subdividiu o índice em
   três padrões construtivos (Econômico, Médio, Alto) e atualizou pesos de
   insumos modernos (aço, alumínio, instalações).
2. **Convenção de encadeamento:** o número-índice base 100 contínuo é
   encadeado pelo produtório exato das variações mensais oficiais do BCB —
   compare períodos pelas variações (`variacao_mensal_percentual`, YTD,
   12m/24m/36m), não por número-índice isolado de séries distintas (§4.1).
3. **Integridade:** coletas com UPSERT idempotente e auditoria.

## Relação entre as variantes

`incc_compare()` devolve o spread INCC-M − INCC-DI em pontos percentuais
para o mesmo mês (janelas de coleta diferentes — não é comparar datas
civis iguais, é a leitura oficial de cada variante)."""

_USO = """\
# AutoINCC — guia de uso das tools (§2.1)

## Fluxo recomendado

1. `incc_metadata()` — catálogo das séries e notas metodológicas
   (resource `autoincc://guia/series`).
2. `incc_latest(sigla)` — mês corrente da série (default `INCC-M`).
3. `incc_history(data_inicio, data_fim, sigla)` — recorte histórico
   (**datas obrigatórias**, formato `AAAA-MM-DD`, `skip`/`limit` paginação).
4. `incc_correction(...)` — correção por período; `incc_overview()` —
   visão geral das duas variantes; `incc_compare()` — spread do mês.
5. `incc_stats(sigla, ano_inicio, ano_fim)` — estatísticas de janela;
   `incc_seasonality(sigla)` — sazonalidade.

## Janelas de `incc_stats` (contrato §4.4)

- **Sem** `ano_inicio`/`ano_fim`: janela **padrão de 120 observações** (10
  anos) até o mês corrente; o payload declara `janela {ano_inicio, ano_fim,
  padrao: true}` e `total_observacoes`.
- **Com** `ano_inicio`/`ano_fim`: recorte por ano civil (ex.: 2020–2024 =
  60 observações, `padrao: false`).
- Janela invertida (`ano_inicio > ano_fim`) = erro **422**.

## Exemplos

- `incc_latest({"sigla": "INCC-M"})` → mês corrente (default sem arg.)
- `incc_history({"data_inicio": "2024-01-01", "data_fim": "2024-12-31"})`
- `incc_stats({"sigla": "INCC-M"})` → janela padrão de 120 observações
- `incc_stats({"sigla": "INCC-DI", "ano_inicio": 2020, "ano_fim": 2024})`
- `incc_compare({})` → spread INCC-M − INCC-DI do mês corrente
"""


def register_resources(server) -> None:
    """Registra os resources legíveis por agente no FastMCP (§2.1).

    ``server`` é a instância ``FastMCP`` devolvida por ``create_server()``;
    a função não importa o módulo ``server`` (evita import circular).
    """

    @server.resource(
        "autoincc://guia/series",
        name="Séries INCC e metodologia",
        description=(
            "Catálogo das séries INCC-M (BCB 192) e INCC-DI (BCB 7456): "
            "janelas de coleta, cobertura, convenção de encadeamento base "
            "100 e notas metodológicas oficiais."
        ),
        mime_type="text/markdown",
    )
    def series() -> str:
        return _SERIES

    @server.resource(
        "autoincc://guia/uso",
        name="Guia de uso das tools INCC",
        description=(
            "Fluxo das tools (latest → history/correction/compare), "
            "contrato de janela do incc_stats (default 120 observações, "
            "422 em janela invertida) e exemplos de chamada."
        ),
        mime_type="text/markdown",
    )
    def guia_uso() -> str:
        return _USO
