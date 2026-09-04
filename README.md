# 🏗️ AutoINCC API

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15%2B-4169E1.svg?logo=postgresql)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7%2B-DC382D.svg?logo=redis)](https://redis.io/)
[![Celery](https://img.shields.io/badge/Celery-5.3%2B-37814A.svg?logo=celery)](https://docs.celeryq.dev/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg?logo=docker)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**AutoINCC** é uma plataforma open-source e API RESTful de alta performance projetada para automatizar a extração, transformação, cálculo econômico e disponibilização do **Índice Nacional de Custo da Construção (INCC)**. 

Concebido como projeto irmão do [AutoSINAPI](https://github.com/LAMP-LUCAS/autoSINAPI_API) e do [AutoCUB](https://github.com/LAMP-LUCAS/autoCUB_API) dentro do ecossistema de dados abertos para a construção civil (**Mundo AEC**), o AutoINCC adota a mesma arquitetura de microsserviços distribuídos de alta disponibilidade: **FastAPI + Redis + Celery + PostgreSQL (Star Schema)**.

---

## 🏛️ Arquitetura de Microsserviços & Resiliência

```text
                               ┌───────────────────────────────────┐
                               │         FastAPI (REST API)        │
                               └─────────┬───────────────▲─────────┘
                                         │               │
                             1. Dispara  │               │ 3. Consulta Cache L2
                                task     │               │    (< 3ms)
                                         ▼               │
                               ┌─────────────────────────┴─────────┐
                               │               REDIS               │
                               │    (Broker Celery + Cache L2)     │
                               └─────────┬─────────────────────────┘
                                         │
                              2. Consome │ Invalida / Aquece
                                 tarefas │ cache pós-ETL
                                         ▼
                               ┌───────────────────────────────────┐
                               │        Celery ETL Worker          │
                               │      (Worker Assíncrono)          │
                               └─────────┬─────────────────────────┘
                                         │
                                         │ 4. UPSERT Idempotente
                                         ▼
                               ┌───────────────────────────────────┐
                               │            PostgreSQL             │
                               │         (Star Schema DW)          │
                               └───────────────────────────────────┘

                     Orquestrador de Inicialização (Container 'init'):
                       Postgres & Redis Saudáveis ──▶ Init Executa DDL/Seed ──▶ Encerra com Sucesso (0)
                                                                                  │
                                            ┌─────────────────────────────────────┴─────────────────────────────────────┐
                                            ▼                                                                           ▼
                                  API inicia com DB 100% pronto                                            Worker inicia pronto para tarefas
```

---

## 🚀 Funcionalidades Principais

- **ETL com Celery Worker Assíncrono:** Extração desacoplada com tolerância a falhas, retentativas e persistência de mensagens no Redis.
- **Cache L2 de Alta Performance (Redis):** Latência de leitura inferior a 3ms para consultas aos índices consolidados (`/latest`) e séries históricas (`/history`), com invalidação automática orientada a eventos pós-carga.
- **Polite Crawling & Request Pacer:** Limitação de taxa ética com jitter estocástico uniforme entre requisições externas ao Banco Central e FGV, evitando bloqueios (HTTP 429) e sobrecargas.
- **Container Init Orquestrador:** Garante inicialização determinística do banco e seed de dimensões via `service_completed_successfully` antes da inicialização da API e dos workers.
- **Rigor Matemático:**
  - Normalização de taxas percentuais ($v_m = \text{valor} / 100$).
  - **Número-Índice Contínuo (Base 100):** Encadeamento de taxas via produtório acumulado histórico ($100 \times \prod (1 + v_m)$).
  - Variação Acumulada no Ano (**YTD** - Year to Date).
  - Variação Acumulada nos Últimos **12 Meses** (janela móvel).
- **Modelo Dimensional (Star Schema):** PostgreSQL com tabelas `dim_tempo`, `dim_categoria`, `dim_geografia`, `dim_tipo_indice` e a tabela `fato_incc` com `UPSERT` nativo (`ON CONFLICT DO UPDATE`).
- **Calculadora de Correção Monetária:** Reajuste de contratos e parcelas pelo fator acumulado do período ($Valor \times \frac{I_{fim}}{I_{inicio}}$).

---

## ⚡ Inicialização Rápida com Docker Compose

Suba todo o ecossistema (Postgres, Redis, Init, API e Celery Worker) com um único comando:

```bash
docker compose up -d --build
```

### Verificação do Status dos Containers
```bash
docker compose ps
```
Você verá o container `autoincc_init` executado com código de saída 0 e todos os serviços saudáveis:
```text
NAME                     IMAGE                        STATUS                    PORTS
autoincc_api             autoincc_api-api             Up (healthy)              0.0.0.0:8000->8000/tcp
autoincc_celery_worker   autoincc_api-celery_worker   Up                        
autoincc_init            autoincc_api-init            Exited (0)                
autoincc_postgres        postgres:15-alpine           Up (healthy)              0.0.0.0:5432->5432/tcp
autoincc_redis           redis:7-alpine               Up (healthy)              0.0.0.0:6379->6379/tcp
```

---

---

## 📚 Endpoints da API (`/api/v1`)

### 1. Raio-X do Mercado & Visão Geral (`/overview`)
Retorna um snapshot consolidado do último mês de referência disponível, com as taxas de ambas as variantes (INCC-M e INCC-DI), spread pontual, variações acumuladas em múltiplas janelas (YTD, 12M, 24M, 36M) e dinâmica de aceleração/momentum.

```http
GET /api/v1/incc/overview
```
*Cache L2 no Redis (`incc:overview`, TTL 3600s).*

**Exemplo de Resposta:**
```json
{
  "data_referencia": "2026-07-01",
  "incc_m": {
    "sigla": "INCC-M",
    "data_id": "2026-07-01",
    "variacao_mensal_percentual": "0.6100",
    "numero_indice": "118.406632",
    "variacao_ytd_percentual": "4.9085",
    "variacao_12m_percentual": "6.4594",
    "variacao_24m_percentual": "14.3580",
    "variacao_36m_percentual": "-100.0000"
  },
  "incc_di": {
    "sigla": "INCC-DI",
    "data_id": "2026-08-01",
    "variacao_mensal_percentual": "0.8500",
    "numero_indice": "119.115357",
    "variacao_ytd_percentual": "5.5900",
    "variacao_12m_percentual": "6.5542",
    "variacao_24m_percentual": null,
    "variacao_36m_percentual": null
  },
  "spread_mensal_pontos": "-0.2400",
  "aceleracao_incc_m": {
    "delta_mes_anterior_pontos": "-0.1700",
    "delta_ano_anterior_pontos": "-0.3000",
    "tendencia": "desacelerando"
  }
}
```

---

### 2. Comparativo Unificado Lado a Lado (`/compare`)
Série temporal unificada e alinhada mês a mês entre INCC-M e INCC-DI, com cálculo automatizado de spread ponto a ponto ($v_{\text{INCC-M}} - v_{\text{INCC-DI}}$) e detecção da variante dominante (`INCC-M`, `INCC-DI` ou `EMPATE`).

```http
GET /api/v1/incc/compare?data_inicio=2024-01-01&data_fim=2024-12-01&skip=0&limit=100
```
*Cache L2 no Redis (`incc:compare:*`, TTL 3600s).*

---

### 3. Matriz de Sazonalidade dos 12 Meses (`/analytics/seasonality`)
Decomposição estatística histórica de longo prazo (1944 até o presente) agregada para cada um dos 12 meses do ano civil (Janeiro a Dezembro), contendo média, mediana, desvio padrão amostral, mínimos, máximos e probabilidade histórica de alta inflacionária.

```http
GET /api/v1/incc/analytics/seasonality?sigla=INCC-M
```
*Cache L2 no Redis (`incc:seasonality:*`, TTL 86400s).*

---

### 4. Estatísticas Agregadas da Série (`/analytics/stats`)
Resumo estatístico da série histórica com volatilidade anualizada ($\sigma \times \sqrt{12}$), média, mediana e identificação dos recordes históricos de alta e baixa com data exata.

```http
GET /api/v1/incc/analytics/stats?sigla=INCC-M
```
*Cache L2 no Redis (`incc:stats:*`, TTL 86400s).*

**Exemplo de Resposta:**
```json
{
  "sigla": "INCC-M",
  "total_observacoes": 990,
  "data_inicio": "1944-02-01",
  "data_fim": "2026-07-01",
  "media_mensal_percentual": "4.0950",
  "mediana_mensal_percentual": "1.0000",
  "desvio_padrao_mensal_pontos": "8.5623",
  "volatilidade_anualizada_percentual": "29.6608",
  "recorde_alta_percentual": "78.4100",
  "recorde_alta_data": "1990-03-01",
  "recorde_baixa_percentual": "-4.4200",
  "recorde_baixa_data": "1945-01-01"
}
```

---

### 5. Catálogo Técnico e Governança Metodológica (`/metadata`)
Exposição dos metadados oficiais das séries (código BCB SGS, instituto responsável, janelas de coleta do mês civil vs período 21 a 20 e histórico de revisões metodológicas do FGV IBRE).

```http
GET /api/v1/incc/metadata
```
*Cache L2 no Redis (`incc:metadata`, TTL 86400s).*

---

### 6. Último Índice Consolidado (`/latest`)
```http
GET /api/v1/incc/latest?sigla=INCC-M
```

### 7. Série Histórica Filtrada (`/history`)
```http
GET /api/v1/incc/history?data_inicio=2024-01-01&data_fim=2024-12-01&sigla=INCC-M&skip=0&limit=100
```

### 8. Calculadora de Reajuste Contratual (`/correction`)
```http
POST /api/v1/incc/correction
Content-Type: application/json

{
  "valor_inicial": 100000.00,
  "data_inicio": "2024-01-01",
  "data_fim": "2024-06-01",
  "sigla": "INCC-M"
}
```

### 9. Disparo Manual do ETL via Celery Worker (Protegido)
```http
POST /api/v1/etl/trigger
X-API-Key: autoincc_secret_token_dev_123
Content-Type: application/json

{
  "series_codes": [192, 7456],
  "data_inicial": "2024-01-01"
}
```

---

## 🧪 Testes Automatizados (TDD)

A suíte completa conta com **37 testes automatizados** cobrindo domínio (DDD), modelos matemáticos, resiliência do cache Redis, limitação ética (pacing) e adaptadores HTTP FastAPI:

```bash
pytest -v
```

---

## 📄 Licença

Distribuído sob a licença MIT. Consulte `LICENSE` para mais detalhes.

