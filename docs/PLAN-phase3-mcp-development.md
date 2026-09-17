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

Implementação e integração não foram executadas nesta revisão documental. Observações estáticas indicam pontos de revisão, não exploração confirmada ou breach.
