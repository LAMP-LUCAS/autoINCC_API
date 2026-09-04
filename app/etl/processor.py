"""Data transformation and mathematical computation engine for INCC series.

Transforms raw observations from BCB SGS into normalized fact records and
dimensional temporal entities, calculating continuous chain base-100 index,
Year-to-Date (YTD), and 12-month rolling accumulated rates.
"""

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from app.core.logging import get_logger

logger = get_logger(__name__)

MESES_PT_BR = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}


class INCCProcessor:
    """Processor class responsible for data cleaning, normalization and economic index computations."""

    @staticmethod
    def parse_raw_bcb_data(raw_data: List[Dict[str, Any]]) -> pd.DataFrame:
        """Converts raw BCB JSON list into a typed pandas DataFrame.

        Args:
            raw_data (List[Dict[str, Any]]): List of dicts with keys 'data' (DD/MM/YYYY) and 'valor' (str/float).

        Returns:
            pd.DataFrame: DataFrame sorted by date with columns ['data_id', 'valor_raw', 'variacao_mensal'].
        """
        if not raw_data:
            return pd.DataFrame(columns=["data_id", "valor_raw", "variacao_mensal"])

        df = pd.DataFrame(raw_data)

        # Parse date from 'DD/MM/YYYY' and set day to 01
        df["data_dt"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
        df["data_id"] = df["data_dt"].apply(lambda d: date(d.year, d.month, 1))

        # Clean numerical values (replace comma if present, cast to float)
        df["valor_raw"] = df["valor"].astype(str).str.replace(",", ".").astype(float)

        # Normalize rate: 0.54% -> 0.0054
        df["variacao_mensal"] = df["valor_raw"] / 100.0

        # Sort chronologically and drop duplicates on data_id
        df = df.sort_values(by="data_id").drop_duplicates(subset=["data_id"]).reset_index(drop=True)
        return df

    @classmethod
    def calculate_temporal_dimensions(cls, df: pd.DataFrame) -> pd.DataFrame:
        """Enriches dataframe with time dimension attributes (ano, mes, trimestre, semestre, nome_mes).

        Args:
            df (pd.DataFrame): DataFrame containing 'data_id'.

        Returns:
            pd.DataFrame: DataFrame with additional temporal columns.
        """
        if df.empty:
            return df

        df["ano"] = df["data_id"].apply(lambda d: d.year)
        df["mes"] = df["data_id"].apply(lambda d: d.month)
        df["trimestre"] = df["mes"].apply(lambda m: (m - 1) // 3 + 1)
        df["semestre"] = df["mes"].apply(lambda m: 1 if m <= 6 else 2)
        df["nome_mes"] = df["mes"].map(MESES_PT_BR)
        return df

    @classmethod
    def calculate_metrics(
        cls,
        df: pd.DataFrame,
        base_index: float = 100.0,
        initial_cumulative_factor: float = 1.0,
    ) -> pd.DataFrame:
        r"""Calculates continuous base-100 index, Year-to-Date (YTD), and 12-month rolling variations.

        Mathematical Definitions:
            1. numero_indice:
               I_t = base_index * \prod_{k=1}^{t} (1 + v_{m, k})
            2. variacao_ytd:
               v_{YTD, t} = \prod_{k \in \text{ano } A \le t} (1 + v_{m, k}) - 1
            3. variacao_12m:
               v_{12m, t} = \prod_{k=t-11}^{t} (1 + v_{m, k}) - 1

        Args:
            df (pd.DataFrame): DataFrame with 'variacao_mensal', 'ano', 'mes' sorted chronologically.
            base_index (float): Starting base index value (default 100.0).
            initial_cumulative_factor (float): Multiplier for chaining new batches to past historical indexes.

        Returns:
            pd.DataFrame: Enriched DataFrame with 'numero_indice', 'variacao_ytd', 'variacao_12m'.
        """
        if df.empty:
            return df

        # Step 1: Growth factor (1 + v_m)
        factor = 1.0 + df["variacao_mensal"]

        # Step 2: Continuous chained index calculation via cumulative product
        cumulative_product = factor.cumprod() * initial_cumulative_factor
        df["numero_indice"] = base_index * cumulative_product

        # Step 3: Year-to-Date (YTD) variation grouped by calendar year
        # For each year, product of (1 + v_m) from Jan to current month minus 1
        df["variacao_ytd"] = df.groupby("ano")["variacao_mensal"].transform(
            lambda s: (1.0 + s).cumprod() - 1.0
        )

        # Step 4: 12-month rolling accumulated variation (last 12 monthly rates product minus 1)
        df["variacao_12m"] = (
            factor.rolling(window=12, min_periods=12).apply(np.prod, raw=True) - 1.0
        )

        return df

    @classmethod
    def process_series(
        cls,
        raw_data: List[Dict[str, Any]],
        tipo_id: int,
        categoria_id: int = 1,
        cidade_id: int = 1,
        base_index: float = 100.0,
        initial_cumulative_factor: float = 1.0,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Main transformation pipeline for a series.

        Args:
            raw_data (List[Dict[str, Any]]): Raw JSON observations from BCB.
            tipo_id (int): Index type foreign key (1=INCC-M, 2=INCC-DI).
            categoria_id (int): Category foreign key (default 1 = Geral).
            cidade_id (int): Geography foreign key (default 1 = Nacional).
            base_index (float): Starting base for index.
            initial_cumulative_factor (float): Cumulative factor chaining.

        Returns:
            Tuple[pd.DataFrame, pd.DataFrame]:
                - df_tempo: DataFrame formatted for `dim_tempo` (columns: data_id, ano, mes, trimestre, semestre, nome_mes)
                - df_fato: DataFrame formatted for `fato_incc` (columns: data_id, categoria_id, cidade_id, tipo_id,
                           variacao_mensal, variacao_ytd, variacao_12m, numero_indice)
        """
        logger.info("Processing %d raw records for tipo_id=%d", len(raw_data), tipo_id)
        df = cls.parse_raw_bcb_data(raw_data)
        if df.empty:
            logger.warning("Empty dataframe after parsing raw BCB data for tipo_id=%d", tipo_id)
            return pd.DataFrame(), pd.DataFrame()

        df = cls.calculate_temporal_dimensions(df)
        df = cls.calculate_metrics(
            df=df,
            base_index=base_index,
            initial_cumulative_factor=initial_cumulative_factor,
        )

        # Add foreign key columns
        df["categoria_id"] = categoria_id
        df["cidade_id"] = cidade_id
        df["tipo_id"] = tipo_id

        # Extract DimTempo records
        dim_tempo_cols = ["data_id", "ano", "mes", "trimestre", "semestre", "nome_mes"]
        df_tempo = df[dim_tempo_cols].drop_duplicates(subset=["data_id"]).copy()

        # Extract FatoINCC records
        fato_cols = [
            "data_id",
            "categoria_id",
            "cidade_id",
            "tipo_id",
            "variacao_mensal",
            "variacao_ytd",
            "variacao_12m",
            "numero_indice",
        ]
        df_fato = df[fato_cols].copy()

        # Replace NaN with None for nullable decimal columns (astype(object) prevents pandas float coercion)
        df_fato["variacao_ytd"] = df_fato["variacao_ytd"].astype(object).apply(lambda v: None if pd.isna(v) else round(float(v), 6))
        df_fato["variacao_12m"] = df_fato["variacao_12m"].astype(object).apply(lambda v: None if pd.isna(v) else round(float(v), 6))
        df_fato["variacao_mensal"] = df_fato["variacao_mensal"].apply(lambda v: round(float(v), 6))
        df_fato["numero_indice"] = df_fato["numero_indice"].apply(lambda v: round(float(v), 6))

        logger.info(
            "Successfully transformed %d records (tempo=%d, fato=%d) for tipo_id=%d",
            len(df),
            len(df_tempo),
            len(df_fato),
            tipo_id,
        )
        return df_tempo, df_fato
