"""Unit tests for INCCProcessor mathematical logic and data normalization."""

from datetime import date
from typing import Any, Dict, List
import pytest
import pandas as pd
import numpy as np

from app.etl.processor import INCCProcessor


def test_parse_raw_bcb_data() -> None:
    """Verifies parsing of BCB JSON format into clean normalized DataFrame."""
    raw_data: List[Dict[str, Any]] = [
        {"data": "01/01/2024", "valor": "0.50"},
        {"data": "01/02/2024", "valor": "1.25"},
        {"data": "01/03/2024", "valor": "-0.10"},
    ]

    df = INCCProcessor.parse_raw_bcb_data(raw_data)

    assert len(df) == 3
    assert list(df["data_id"]) == [date(2024, 1, 1), date(2024, 2, 1), date(2024, 3, 1)]

    # 0.50% -> 0.0050
    assert pytest.approx(df.loc[0, "variacao_mensal"], 1e-6) == 0.0050
    # 1.25% -> 0.0125
    assert pytest.approx(df.loc[1, "variacao_mensal"], 1e-6) == 0.0125
    # -0.10% -> -0.0010
    assert pytest.approx(df.loc[2, "variacao_mensal"], 1e-6) == -0.0010


def test_calculate_temporal_dimensions() -> None:
    """Tests date dimension enrichment (ano, mes, trimestre, semestre, nome_mes)."""
    raw_data = [
        {"data": "01/01/2024", "valor": "0.5"},
        {"data": "01/07/2024", "valor": "0.8"},
    ]
    df = INCCProcessor.parse_raw_bcb_data(raw_data)
    df = INCCProcessor.calculate_temporal_dimensions(df)

    assert df.loc[0, "ano"] == 2024
    assert df.loc[0, "mes"] == 1
    assert df.loc[0, "trimestre"] == 1
    assert df.loc[0, "semestre"] == 1
    assert df.loc[0, "nome_mes"] == "Janeiro"

    assert df.loc[1, "ano"] == 2024
    assert df.loc[1, "mes"] == 7
    assert df.loc[1, "trimestre"] == 3
    assert df.loc[1, "semestre"] == 2
    assert df.loc[1, "nome_mes"] == "Julho"


def test_numero_indice_cumulative_product() -> None:
    """Tests the critical calculation of continuous base-100 chain index via cumulative product."""
    raw_data = [
        {"data": "01/01/2024", "valor": "1.00"},  # v_m = 0.01
        {"data": "01/02/2024", "valor": "2.00"},  # v_m = 0.02
        {"data": "01/03/2024", "valor": "3.00"},  # v_m = 0.03
    ]
    df = INCCProcessor.parse_raw_bcb_data(raw_data)
    df = INCCProcessor.calculate_temporal_dimensions(df)
    df = INCCProcessor.calculate_metrics(df, base_index=100.0)

    # Month 1: 100 * 1.01 = 101.0
    expected_idx_1 = 100.0 * 1.01
    assert pytest.approx(df.loc[0, "numero_indice"], 1e-5) == expected_idx_1

    # Month 2: 101.0 * 1.02 = 103.02
    expected_idx_2 = expected_idx_1 * 1.02
    assert pytest.approx(df.loc[1, "numero_indice"], 1e-5) == expected_idx_2

    # Month 3: 103.02 * 1.03 = 106.1106
    expected_idx_3 = expected_idx_2 * 1.03
    assert pytest.approx(df.loc[2, "numero_indice"], 1e-5) == expected_idx_3


def test_variacao_ytd_resets_annually() -> None:
    """Tests that Year-to-Date (YTD) accumulates within the year and resets in January."""
    raw_data = [
        {"data": "01/11/2023", "valor": "1.00"},  # 2023-11: 1%
        {"data": "01/12/2023", "valor": "2.00"},  # 2023-12: 2% -> YTD = (1.01 * 1.02) - 1 = 0.0302
        {"data": "01/01/2024", "valor": "0.50"},  # 2024-01: 0.5% -> YTD resets to 0.0050
        {"data": "01/02/2024", "valor": "1.00"},  # 2024-02: 1% -> YTD = (1.005 * 1.01) - 1
    ]
    df = INCCProcessor.parse_raw_bcb_data(raw_data)
    df = INCCProcessor.calculate_temporal_dimensions(df)
    df = INCCProcessor.calculate_metrics(df)

    # 2023-11: first in year 2023 -> 0.01
    assert pytest.approx(df.loc[0, "variacao_ytd"], 1e-5) == 0.0100

    # 2023-12: (1.01 * 1.02) - 1 = 0.0302
    assert pytest.approx(df.loc[1, "variacao_ytd"], 1e-5) == 0.0302

    # 2024-01: New year reset -> 0.0050
    assert pytest.approx(df.loc[2, "variacao_ytd"], 1e-5) == 0.0050

    # 2024-02: (1.005 * 1.01) - 1 = 0.01505
    expected_ytd_feb = (1.005 * 1.01) - 1.0
    assert pytest.approx(df.loc[3, "variacao_ytd"], 1e-5) == expected_ytd_feb


def test_variacao_12m_rolling() -> None:
    """Tests 12-month rolling accumulated variation."""
    # Generate 14 months of constant 1% (0.01) monthly inflation
    raw_data = [
        {"data": f"01/{m:02d}/2023", "valor": "1.00"} for m in range(1, 13)
    ] + [
        {"data": "01/01/2024", "valor": "1.00"},
        {"data": "01/02/2024", "valor": "1.00"},
    ]

    df = INCCProcessor.parse_raw_bcb_data(raw_data)
    df = INCCProcessor.calculate_temporal_dimensions(df)
    df = INCCProcessor.calculate_metrics(df)

    # For indices 0 to 10 (first 11 months), variacao_12m should be NaN (fewer than 12 periods)
    assert pd.isna(df.loc[0, "variacao_12m"])
    assert pd.isna(df.loc[10, "variacao_12m"])

    # At index 11 (12th month: 2023-12), rolling 12m is (1.01^12) - 1
    expected_12m = (1.01 ** 12) - 1.0
    assert pytest.approx(df.loc[11, "variacao_12m"], 1e-5) == expected_12m

    # At index 12 (13th month: 2024-01), rolling 12m is still (1.01^12) - 1
    assert pytest.approx(df.loc[12, "variacao_12m"], 1e-5) == expected_12m


def test_process_series_empty() -> None:
    """Verifies that empty payload returns empty DataFrames without errors."""
    df_tempo, df_fato = INCCProcessor.process_series([], tipo_id=1)
    assert df_tempo.empty
    assert df_fato.empty
