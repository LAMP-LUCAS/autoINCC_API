# PLAN: Fase 3.2 — desenvolvimento MCP do AutoINCC

> Dono: autoINCC_API. Revisão 2026-09-17; plano proposto, implementação e validação pendentes. Escopo de desenvolvimento do produto.

## Fronteiras e autoridade

AutoINCC é dono das séries, metadados, correção monetária e análises do índice. O adaptador MCP expõe operações aprovadas sem duplicar cálculos, alterar ETL ou criar persistência de projetos. [autoINCC.md](autoINCC.md) oferece contexto de negócio; a definição operacional deve vir do OpenAPI da revisão selecionada.

Entregável proposto: **`autoincc/MCP-Catalog v1`**, publicado e versionado por este produto como única autoridade para catálogo, schemas, erros, transporte, negociação MCP, path, health e configuração suportada. Dependência: **`saas-gateway/MCP-Admission v1`**, ainda sujeito a aprovação/publicação pelo gateway. Referenciar por nome/versão, sem copiar regras comerciais ou depender de localização de outro repositório.

## Sequência de desenvolvimento

1. Mapear operações existentes em `app` e OpenAPI: operationId, método, path, parâmetros, corpo e resposta. Não assumir oito tools nem importar catálogo de outro produto como verdade.
2. Selecionar consultas/análises/correção aprovadas para MCP. Administração e disparos de ETL permanecem fora do catálogo público. Não presumir que POST implica persistência; respeitar a semântica efetiva do caso de uso.
3. Separar transporte, aplicação, cliente de dados e cache; reutilizar validações e cálculos existentes. Confirmar dependências antes da escolha de SDK/bibliotecas.
4. Autenticar cada caller e consumir admissão que vincule contexto MCP confiável à tool, tenant e identidade. `mcp_access` não pode depender de header autodeclarado, de URL REST fornecida pelo cliente ou de qualquer marcador spoofável.
5. Ausência/expiração/revogação de credencial ou indisponibilidade de autorização deve negar execução. Sem API key privilegiada compartilhada de fallback.
6. Autorizar antes de cache hit e particionar dados por tenant, escopo, operação e parâmetros canônicos. Revogação/mudança de plano exige reautorização; seguir contabilização de cache/retry/fan-out definida pelo gateway.
7. Preservar tipo do índice, período, fonte, precisão e avisos de dados incompletos; não extrapolar séries como fatos. Mapear erros tipados sem revelar credenciais.
8. Publicar negociação, transporte e configuração efetivos na versão do contrato, sem deduzir transporte de nomes de paths.

## Aceite e testes locais controlados

- [ ] Matriz tool/OpenAPI aprovada e schemas de entrada/saída testados, sem quantidade ou métodos inventados.
- [ ] Correção e análises reutilizam semântica existente; testes incluem períodos inválidos e ausência de dados.
- [ ] Autenticação e admissão testadas para callers válidos, inválidos/revogados e sem entitlement.
- [ ] Contexto MCP não confiável rejeitado; cache quente não contorna autorização nem cruza tenants.
- [ ] Falhas do gateway negam execução; revogação e mudança de plano cobertas.
- [ ] Sessão, cancelamento, limites, transporte e compatibilidade testados.
- [ ] Release identifica versões OpenAPI/MCP/admissão e evidência de testes, sem declarar código totalmente verificado.

## Adaptador local em desenvolvimento

Pacote independente `autoincc_mcp`, layout src/tools em dois tiers seguindo a referência Matryoshka. Contrato estático: revisão de produto `361634ab7bdb8b7103eaa58f410205d8cb73b62f`, routers montados em `/api/v1`; sem consulta ao OpenAPI runtime. Oito tools solicitadas: latest, history, correction (POST), overview, compare, seasonality, stats e metadata. Stats usa `/api/v1/incc/analytics/stats`; nenhuma tool ETL/admin. Entradas preservam datas, paginação e Decimal; cálculos e respostas ficam sob autoridade REST.

Configuração exclusivamente por ambiente: `AUTOINCC_BASE_URL` usa a constante `DEFAULT_GATEWAY_BASE_URL` (`http://api-gateway-kong:8000`), contrato interno de serviço; `AUTOINCC_CACHE_URL` é opcional, sem fallback de infraestrutura. `AUTOINCC_CACHE_TTL=300`, `AUTOINCC_TIMEOUT=30`, `AUTOINCC_RETRIES=3` (total de tentativas). `AUTOINCC_MCP_PORT=8080`, `AUTOINCC_MCP_HOST=0.0.0.0`, `AUTOINCC_MCP_TRANSPORT=streamable-http` (também SSE e stdio). GET `/sse` é SSE legado; POST `/sse` é Streamable HTTP; `/messages/` recebe mensagens SSE. FastMCP mantém defaults de segurança.

BYOK por chamada, sem chave global e sem leitura de dotenv. Cache Redis usa `autoincc:` + impressão SHA-256 truncada + argumentos canônicos. O cache-aside exige callback confiável de autorização antes da leitura; sem callback, consulta o gateway em toda execução e não lê/escreve cache. Tools não instalam admissão fictícia: integração de `saas-gateway/MCP-Admission v1`, tenant/escopo, revogação e contabilização continuam gates de exposição. Fingerprint não substitui admissão.

Entrega inclui testes isolados e Dockerfiles; sem build Docker ou deployment. O responsável pela integração deve configurar URL/rotas autorizadas do gateway, cache dedicado, admissão antes de cache, rede/ingress e limites. Não alterar o Dockerfile existente da API. Testes locais não aprovam catálogo nem validam runtime.

### Evidências locais

Em 2026-09-17: `pytest -q` — 63 testes aprovados; `ruff check .` e `mypy src` aprovados (9 módulos). Ambiente isolado Python 3.12, MCP SDK 1.30.0; instalação via `pip install --no-deps .` construiu wheel e confirmou `autoincc-mcp = autoincc_mcp:main`. Testes bloqueiam sockets externos, simulam HTTP/Redis e verificam handshake Streamable HTTP, descoberta de 8 tools e lifespan. SSE legado tem roteamento verificado, não sessão ponta a ponta. Dockerfiles usam Python 3.11, ainda não testado em container. `/health` local é liveness no modo combinado, não readiness de gateway/Redis; o healthcheck Docker pressupõe esse modo. `Dockerfile.dev` não configura hot reload.

Nenhuma validação de API live, admissão operacional, build Docker ou deployment foi executada. Cache não serve hits nas tools até integração confiável de admissão; erros de autorização não são cacheados. `BLE001` é excetuado apenas em cache.py para fronteiras de degradação e negação segura. Respostas são JSON REST preservado, sem revalidação contra DTOs duplicados. `history(sigla=None)` envia string vazia para selecionar todas as variantes: omitir o parâmetro REST selecionaria o default INCC-M. Validação e serialização monetária usam Decimal sem conversão para float.
