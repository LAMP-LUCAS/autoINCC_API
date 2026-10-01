"""Dependências FastAPI — autenticação do trigger de ETL (STORY-MCP-009).

O endpoint administrativo `POST /api/v1/etl/trigger` (dispara coleta da FGV)
era protegido por `API_KEY`, que tinha **valor padrão no código**. Qualquer
instalação que não definisse a variável de ambiente subia com uma credencial
pública e o disparo ficava acessível.

Regras daqui em diante (fail-loud, ADR 010):

1. **Sem `API_KEY` configurada, o endpoint fica desabilitado** — responde `503`
   com o motivo nomeado. Não é `403` (seria "chave errada") nem sucesso.
   Serviço de leitura continua funcionando; só o disparo fica fechado.
2. **Chave em branco nunca autentica.** `settings.API_KEY` é tratado como
   ausente se for `None` ou só espaços.
3. **Comparação em tempo constante** (`secrets.compare_digest`), sem
   curto-circuito por tamanho.
4. `X-API-Key` ausente ou errado → `403` (comportamento já existente).
"""
from typing import Optional

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Mensagem de indisponibilidade: nomeia a variável e a ação, sem vazar segredo.
TRIGGER_DESABILITADO = (
    "Trigger de ETL desabilitado: a variável de ambiente API_KEY não está "
    "configurada. Defina-a (e reinicie o serviço) para habilitar o disparo "
    "administrativo — até lá, este endpoint responde 503 por desenho."
)


def _chave_configurada() -> Optional[str]:
    """Chave ativa, ou `None` se não houver (ausente/branca)."""
    bruto = settings.API_KEY
    if bruto is None:
        return None
    limpa = str(bruto).strip()
    return limpa or None


def trigger_habilitado() -> bool:
    """O disparo administrativo está habilitado? (expõe no health)"""
    return _chave_configurada() is not None


def verify_api_key(api_key: Optional[str] = Security(api_key_header)) -> str:
    """Valida a chave administrativa do header `X-API-Key`.

    Returns:
        str: a chave validada.

    Raises:
        HTTPException: `503` se o trigger estiver desabilitado (sem `API_KEY`
            configurada) ou `403` se a chave vier ausente/errada.
    """
    import secrets

    esperada = _chave_configurada()
    if esperada is None:
        # Fail-loud: sem chave configurada o endpoint NÃO existe de fato.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=TRIGGER_DESABILITADO,
        )
    if not api_key or not secrets.compare_digest(str(api_key).strip(), esperada):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Invalid or missing X-API-Key header",
        )
    return str(api_key).strip()


__all__ = ["get_db", "verify_api_key", "trigger_habilitado", "TRIGGER_DESABILITADO"]
