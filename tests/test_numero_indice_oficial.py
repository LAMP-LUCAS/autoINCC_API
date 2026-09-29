"""RED §4.1 — `numero_indice` da série M na escala oficial FGV (base 100 = ago/1994).

Achado da auditoria (§4.1): a cadeia M era encadeada a partir de base 100 em
fev/1944, produzindo número-índice ~1e18 (fator ≈ 8e14 acima da série oficial
FGV publicada). A escala oficial (Sinduscon-PR/FGV, série histórica xlsx) tem
base 100 = 01/08/1994 e ≈ 1.283 para jul/2026.

Evidências-âncora:
- Fixture: variações brutas do BCB SGS 192 (mesma fonte da ETL).
- Oficial: INCC-M jul/2026 = 1.283,035 (FGV/Sinduscon-PR).
- Razão é invariante de escala: `incc_correction` deve continuar idêntico —
  idx(2026-07)/idx(2026-01) == produto independente das variações do BCB
  (referência da auditoria: 1,041586).
"""

from datetime import date
from typing import Any, Dict, List
import json
from pathlib import Path

import pytest

from app.etl.processor import INCCProcessor

FIXTURE = Path(__file__).parent / "fixtures" / "bcb_sgs192_full.json"
BASE_OFICIAL = date(1994, 8, 1)  # base da série oficial FGV = 100
OFICIAL_JUL_2026 = 1283.035  # FGV/Sinduscon-PR
MAX_PLAUSIVEL = 100_000.0  # teto do guard de sanidade no loader


def _raw() -> List[Dict[str, Any]]:
    return json.loads(FIXTURE.read_text())


def _valor_variacao_bruta(d: date) -> float:
    for r in _raw():
        dd, mm, yy = r["data"].split("/")
        if date(int(yy), int(mm), 1) == d:
            return float(r["valor"].replace(",", ".")) / 100.0
    raise AssertionError(f"sem variação bruta para {d}")


@pytest.fixture(scope="module")
def fato_m():
    df_tempo, df_fato = INCCProcessor.process_series(
        _raw(), tipo_id=1, base_date=BASE_OFICIAL
    )
    return df_fato


def _valor_em(fato, d: date) -> float:
    linha = fato[fato["data_id"] == d]
    assert not linha.empty, f"sem observação para {d}"
    return float(linha.iloc[0]["numero_indice"])


def test_mes_base_igual_a_100(fato_m) -> None:
    """A data-base oficial (ago/1994) vale exatamente 100."""
    assert _valor_em(fato_m, date(1994, 8, 1)) == pytest.approx(100.0, abs=1e-9)


def test_janela_recente_em_faixa_plausivel(fato_m) -> None:
    """§4.1: todas as obs. de 2026 em faixa plausível (gate: [50, 5000])."""
    janela = fato_m[fato_m["data_id"] >= date(2026, 1, 1)]
    assert len(janela) >= 7  # jan..jul obrigatório; ago/2026 conforme BCB
    for _, r in janela.iterrows():
        v = float(r["numero_indice"])
        assert 50.0 <= v <= 5000.0, f"{r['data_id']}: {v} fora de [50, 5000]"


def test_ultima_obs_proxima_do_indice_oficial(fato_m) -> None:
    """Série processada ≈ série oficial FGV (tolerância 1%: BCB vs FGV)."""
    v = _valor_em(fato_m, date(2026, 7, 1))
    assert v == pytest.approx(OFICIAL_JUL_2026, rel=0.01)


def test_razao_incc_correction_preservada(fato_m) -> None:
    """Razão jul/jan-2026 == produto independente das variações do BCB
    (referência da auditoria 1,041586) — invariante de escala."""
    produto = 1.0
    for r in _raw():
        dd, mm, yy = r["data"].split("/")
        d = date(int(yy), int(mm), 1)
        if date(2026, 1, 1) < d <= date(2026, 7, 1):
            produto *= 1 + float(r["valor"].replace(",", ".")) / 100.0
    razao = _valor_em(fato_m, date(2026, 7, 1)) / _valor_em(fato_m, date(2026, 1, 1))
    assert razao == pytest.approx(produto, rel=1e-9)
    assert razao == pytest.approx(1.041586, rel=1e-4)  # referência da auditoria


def test_serie_integra_na_faixa(fato_m) -> None:
    """Série inteira preservada (991 obs), toda positiva e ≤ teto — nunca 1e18."""
    assert len(fato_m) == 991
    vals = fato_m["numero_indice"].astype(float)
    assert (vals > 0).all()
    assert vals.max() <= MAX_PLAUSIVEL


def test_pre_base_mantem_continuidade(fato_m) -> None:
    """Obs. anteriores à base ficam em (0, 100) e a razão contínua é 1 + v."""
    jul = _valor_em(fato_m, date(1994, 7, 1))
    ago = _valor_em(fato_m, date(1994, 8, 1))
    assert 0 < jul < ago == pytest.approx(100.0, abs=1e-9)
    assert ago / jul == pytest.approx(1.0 + _valor_variacao_bruta(date(1994, 8, 1)), rel=1e-9)


def test_base_date_ausente_falha_em_vez_de_persistir_escala_errada() -> None:
    """`base_date` fora da série → erro explícito; nunca carga silenciosa
    na escala errada (a falha de escala é justamente o defeito §4.1)."""
    with pytest.raises(ValueError):
        INCCProcessor.process_series(_raw(), tipo_id=1, base_date=date(1940, 1, 1))
