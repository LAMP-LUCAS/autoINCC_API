"""STORY-MCP-009 · segurança: o trigger de ETL não pode abrir com chave de dev.

Achado (2026-10-01, revisão de documentação): a chave que protege
`POST /api/v1/etl/trigger` tinha **valor padrão no código**
(`app/core/config.py`), replicado no `docker-compose.yml` e no README. Qualquer
instalação que não definisse a variável de ambiente subia com uma credencial
pública e o disparo de ETL (que baixa dados da FGV) ficava acessível.

Correção (fail-loud, ADR 010):

1. `API_KEY` deixa de ter default — sem valor, o serviço sobe mas o endpoint
   fica **desabilitado explicitamente** (503 com motivo nomeado), em vez de
   aceitar a chave conocida.
2. Chave em branco/branco nunca autentica (comparação com `secrets.compare_digest`,
   sem curto-circuito por timing).
3. O health reporta se o trigger está habilitado, para o risco ficar visível.
4. `docker-compose.yml` passa a exigir a variável; `.env.example` só com
   placeholder.

A chave antiga está no histórico Git: **é preciso rotacionar** em qualquer
ambiente onde o trigger ficou exposto.
"""
import pytest

from app.api import deps
from app.core.config import settings


def test_sem_api_key_configurada_o_trigger_fica_desabilitado(monkeypatch):
    """A falha que corrigimos: sem chave, o endpoint NÃO pode aceitar a chave
    de dev — nem nenhuma."""
    monkeypatch.setattr(deps.settings, "API_KEY", None, raising=False)
    with pytest.raises(deps.HTTPException) as exc:
        deps.verify_api_key(api_key="autoincc_secret_token_dev_123")
    assert exc.value.status_code == 503
    assert "API_KEY" in str(exc.value.detail)


def test_chave_de_dev_nao_autentica_quando_nao_configurada(monkeypatch):
    """O teste que FALHA no código antigo: a chave pública de dev aceitava."""
    monkeypatch.setattr(deps.settings, "API_KEY", "", raising=False)
    with pytest.raises(deps.HTTPException) as exc:
        deps.verify_api_key(api_key="autoincc_secret_token_dev_123")
    assert exc.value.status_code == 503


def test_api_key_em_branco_nunca_autentica(monkeypatch):
    """Chave configurada vazia/branca não pode casar com header vazio/branco."""
    monkeypatch.setattr(deps.settings, "API_KEY", "   ", raising=False)
    for header in ("", "   ", None):
        with pytest.raises(deps.HTTPException):
            deps.verify_api_key(api_key=header)


def test_chave_errada_da_403(monkeypatch):
    monkeypatch.setattr(deps.settings, "API_KEY", "chave-certa-xyz", raising=False)
    with pytest.raises(deps.HTTPException) as exc:
        deps.verify_api_key(api_key="chave-errada")
    assert exc.value.status_code == 403


def test_chave_certa_passa(monkeypatch):
    monkeypatch.setattr(deps.settings, "API_KEY", "chave-certa-xyz", raising=False)
    assert deps.verify_api_key(api_key="chave-certa-xyz") == "chave-certa-xyz"


def test_settings_nao_tem_default_de_chave():
    """O default hardcoded é a raiz do problema — não pode voltar."""
    from app.core.config import Settings

    # o default precisa ser ausente/vazio, nunca um valor de dev
    padrao = Settings.model_fields["API_KEY"].get_default(call_default_factory=True)
    assert padrao in (None, ""), f"API_KEY ainda tem default: {padrao!r}"


def test_health_reporta_se_o_trigger_esta_habilitado(monkeypatch):
    """O risco precisa ficar visível, não só fechado (STORY-MCP-009)."""
    from app import main as main_mod
    from app.api import deps

    monkeypatch.setattr(deps.settings, "API_KEY", "chave-certa-xyz", raising=False)
    assert main_mod.health_check()["etl_trigger_habilitado"] is True

    monkeypatch.setattr(deps.settings, "API_KEY", None, raising=False)
    assert main_mod.health_check()["etl_trigger_habilitado"] is False
