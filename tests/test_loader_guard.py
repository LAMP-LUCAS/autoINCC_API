"""REENG §4.1 — asserção de sanidade no loader: nunca persistir número-índice
fora da faixa plausível (falhar em vez de gravar silenciosamente)."""

from datetime import date
from typing import Any, Dict
import pandas as pd
import pytest

from app.db.models import FatoINCC
from app.etl.loader import INCCLoader


def _df_com_indice(valor: float) -> pd.DataFrame:
    row: Dict[str, Any] = {
        "data_id": date(2026, 7, 1),
        "categoria_id": 1,
        "cidade_id": 1,
        "tipo_id": 1,
        "variacao_mensal": 0.0061,
        "variacao_ytd": 0.0470,
        "variacao_12m": 0.0640,
        "numero_indice": valor,
    }
    return pd.DataFrame([row])


def test_upsert_rejeita_indice_corrompido(db_session) -> None:
    """Cadeia 1944 (fator ≈ 1e15, achado §4.1) nunca é persistida."""
    loader = INCCLoader(db_session)
    with pytest.raises(ValueError, match="faixa"):
        loader.upsert_fato_incc(_df_com_indice(1083477441865997000.0))
    assert db_session.query(FatoINCC).count() == 0


def test_upsert_rejeita_indice_negativo_ou_nulo(db_session) -> None:
    loader = INCCLoader(db_session)
    with pytest.raises(ValueError, match="faixa"):
        loader.upsert_fato_incc(_df_com_indice(-5.0))
    assert db_session.query(FatoINCC).count() == 0


def test_upsert_aceita_indice_na_escala_oficial(db_session) -> None:
    """Valores na escala oficial FGV (≈1.283 em jul/2026) persistem normalmente."""
    loader = INCCLoader(db_session)
    n = loader.upsert_fato_incc(_df_com_indice(1283.035))
    assert n == 1
    assert db_session.query(FatoINCC).count() == 1
