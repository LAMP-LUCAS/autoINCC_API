"""§4.3 da auditoria (P1) — `incc_metadata` fiel aos dados armazenados.

RED comportamental (igual ao gate da casa `verify_mcp_audit_claims.py`):
`inicio_serie` vinha de CONSTANTE (`"1944"` em `analytics_service`) — para
INCC-DI o dado armazenado só existe desde 2024-01 (carga inicial
`data_inicial=2024-01-01`) e o gate falha:

    INCC-DI: declara 1944, sem dado em 1944

Correção proposta pela auditoria (§4.3): derivar `inicio_serie` da primeira
observação efetivamente armazenada e expor `observacoes_disponiveis`.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import DimTempo, FatoINCC
from app.db.session import seed_default_dimensions


def _seed_obs(db_session: Session, tipo_id: int, data_id: date) -> None:
    tempo = db_session.query(DimTempo).filter_by(data_id=data_id).first()
    if not tempo:
        mes = data_id.month
        db_session.add(
            DimTempo(
                data_id=data_id,
                ano=data_id.year,
                mes=mes,
                trimestre=(mes - 1) // 3 + 1,
                semestre=1 if mes <= 6 else 2,
                nome_mes="ref",
            )
        )
    db_session.add(
        FatoINCC(
            data_id=data_id,
            categoria_id=1,
            cidade_id=1,
            tipo_id=tipo_id,  # 1 = INCC-M, 2 = INCC-DI (seed_default_dimensions)
            variacao_mensal=Decimal("0.005"),
            variacao_ytd=Decimal("0.005"),
            variacao_12m=None,
            numero_indice=Decimal("100.500000"),
        )
    )
    db_session.commit()


def test_metadata_inicio_serie_reflete_dados_armazenados(
    client: TestClient, db_session: Session
) -> None:
    seed_default_dimensions(db_session)

    # INCC-M: dado real desde 1944-02 (reprocesso da Fase 1 §4.1)
    _seed_obs(db_session, 1, date(1944, 2, 1))
    _seed_obs(db_session, 1, date(1944, 3, 1))
    # INCC-DI: só existe dado desde 2024-01
    _seed_obs(db_session, 2, date(2024, 1, 1))
    _seed_obs(db_session, 2, date(2024, 2, 1))

    resp = client.get("/api/v1/incc/metadata")
    assert resp.status_code == 200
    series = {s["sigla"]: s for s in resp.json()["series"]}

    m = series["INCC-M"]
    di = series["INCC-DI"]

    # pin: M tem dado desde 1944 → continua declarando 1944
    assert str(m["inicio_serie"])[:4] == "1944"

    # §4.3: INCC-DI deve declarar o ano da PRIMEIRA observação armazenada
    # (hoje: constante "1944" → RED, sem dado em 1944)
    assert str(di["inicio_serie"])[:4] == "2024", (
        f"inicio_serie deve derivar do dado armazenado, veio {di['inicio_serie']!r} (§4.3)"
    )

    # auditoria §4.3: expor quantas observações cada série tem
    assert m.get("observacoes_disponiveis") == 2, "INCC-M sem observacoes_disponiveis (§4.3)"
    assert di.get("observacoes_disponiveis") == 2, "INCC-DI sem observacoes_disponiveis (§4.3)"


def test_metadata_sem_dado_declara_observacoes_zero(
    client: TestClient, db_session: Session
) -> None:
    """Série sem NENHUM dado armazenado declara 0 observações — nunca inventa
    início."""
    seed_default_dimensions(db_session)

    resp = client.get("/api/v1/incc/metadata")
    assert resp.status_code == 200
    for s in resp.json()["series"]:
        assert s.get("observacoes_disponiveis") == 0, (
            f"{s['sigla']}: sem dado armazenado deve declarar 0 observações"
        )
