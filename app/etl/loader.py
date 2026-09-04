"""Database loader module executing idempotent UPSERTs on Star Schema tables.

Uses PostgreSQL native `INSERT ... ON CONFLICT DO UPDATE` via SQLAlchemy dialect,
with fallback support for SQLite during automated test runs.
"""

from typing import Any, Dict, List, Optional
import pandas as pd
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models import DimCategoria, DimGeografia, DimTempo, DimTipoIndice, FatoINCC
from app.db.session import seed_default_dimensions

logger = get_logger(__name__)


class INCCLoader:
    """Handles persistent storage and UPSERT operations for AutoINCC Star Schema."""

    def __init__(self, session: Session) -> None:
        """Initializes the loader with an active database session.

        Args:
            session (Session): SQLAlchemy session.
        """
        self.session = session
        self.dialect_name = session.bind.dialect.name if session.bind else "postgresql"

    def ensure_baseline_dimensions(self) -> None:
        """Verifies and seeds baseline categorical, geographic, and index type dimensions."""
        seed_default_dimensions(self.session)

    def upsert_dim_tempo(self, df_tempo: pd.DataFrame) -> int:
        """Inserts temporal dimension records, ignoring conflicts on data_id.

        Args:
            df_tempo (pd.DataFrame): DataFrame with columns (data_id, ano, mes, trimestre, semestre, nome_mes).

        Returns:
            int: Number of records processed.
        """
        if df_tempo.empty:
            logger.info("No DimTempo records to upsert.")
            return 0

        records: List[Dict[str, Any]] = df_tempo.to_dict(orient="records")
        logger.info("Upserting %d records into dim_tempo (dialect=%s)", len(records), self.dialect_name)

        if self.dialect_name == "postgresql":
            stmt = pg_insert(DimTempo).values(records)
            stmt = stmt.on_conflict_do_nothing(index_elements=["data_id"])
            self.session.execute(stmt)
        elif self.dialect_name == "sqlite":
            stmt_sqlite = sqlite_insert(DimTempo).values(records)
            stmt_sqlite = stmt_sqlite.on_conflict_do_nothing(index_elements=["data_id"])
            self.session.execute(stmt_sqlite)
        else:
            # Generic fallback
            for rec in records:
                existing = self.session.query(DimTempo).filter_by(data_id=rec["data_id"]).first()
                if not existing:
                    self.session.add(DimTempo(**rec))

        self.session.commit()
        logger.info("dim_tempo upsert completed successfully.")
        return len(records)

    def upsert_fato_incc(self, df_fato: pd.DataFrame) -> int:
        """Inserts or updates fact records on composite primary key (data_id, categoria_id, cidade_id, tipo_id).

        Args:
            df_fato (pd.DataFrame): DataFrame with fact metrics.

        Returns:
            int: Number of fact rows processed.
        """
        if df_fato.empty:
            logger.info("No FatoINCC records to upsert.")
            return 0

        records: List[Dict[str, Any]] = df_fato.to_dict(orient="records")
        logger.info("Upserting %d records into fato_incc (dialect=%s)", len(records), self.dialect_name)

        if self.dialect_name == "postgresql":
            stmt = pg_insert(FatoINCC).values(records)
            stmt = stmt.on_conflict_do_update(
                index_elements=["data_id", "categoria_id", "cidade_id", "tipo_id"],
                set_={
                    "variacao_mensal": stmt.excluded.variacao_mensal,
                    "variacao_ytd": stmt.excluded.variacao_ytd,
                    "variacao_12m": stmt.excluded.variacao_12m,
                    "numero_indice": stmt.excluded.numero_indice,
                    "updated_at": func.now(),
                },
            )
            self.session.execute(stmt)
        elif self.dialect_name == "sqlite":
            stmt_sqlite = sqlite_insert(FatoINCC).values(records)
            stmt_sqlite = stmt_sqlite.on_conflict_do_update(
                index_elements=["data_id", "categoria_id", "cidade_id", "tipo_id"],
                set_={
                    "variacao_mensal": stmt_sqlite.excluded.variacao_mensal,
                    "variacao_ytd": stmt_sqlite.excluded.variacao_ytd,
                    "variacao_12m": stmt_sqlite.excluded.variacao_12m,
                    "numero_indice": stmt_sqlite.excluded.numero_indice,
                    "updated_at": func.now(),
                },
            )
            self.session.execute(stmt_sqlite)
        else:
            for rec in records:
                existing = (
                    self.session.query(FatoINCC)
                    .filter_by(
                        data_id=rec["data_id"],
                        categoria_id=rec["categoria_id"],
                        cidade_id=rec["cidade_id"],
                        tipo_id=rec["tipo_id"],
                    )
                    .first()
                )
                if existing:
                    existing.variacao_mensal = rec["variacao_mensal"]
                    existing.variacao_ytd = rec["variacao_ytd"]
                    existing.variacao_12m = rec["variacao_12m"]
                    existing.numero_indice = rec["numero_indice"]
                else:
                    self.session.add(FatoINCC(**rec))

        self.session.commit()
        logger.info("fato_incc upsert completed successfully.")
        return len(records)
