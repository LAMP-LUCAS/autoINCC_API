"""Database session management and engine initialization."""

from typing import Generator
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import Base, DimCategoria, DimGeografia, DimTipoIndice

logger = get_logger(__name__)

# Configure engine with connection pooling
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=settings.DEBUG and settings.APP_ENV == "development",
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a transactional database session.

    Yields:
        Session: Active SQLAlchemy session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def seed_default_dimensions(session: Session) -> None:
    """Seeds essential dimensions (Geral, Nacional, INCC-M, INCC-DI) if empty.

    Args:
        session (Session): Active SQLAlchemy session.
    """
    # 1. Seed DimCategoria
    categoria_geral = session.execute(
        select(DimCategoria).where(DimCategoria.categoria_id == 1)
    ).scalar_one_or_none()
    if not categoria_geral:
        session.add(
            DimCategoria(
                categoria_id=1,
                nome_categoria="Geral",
                descricao="Índice Geral do INCC consolidado",
            )
        )

    # 2. Seed DimGeografia
    geografia_nacional = session.execute(
        select(DimGeografia).where(DimGeografia.cidade_id == 1)
    ).scalar_one_or_none()
    if not geografia_nacional:
        session.add(
            DimGeografia(
                cidade_id=1,
                nome_cidade="Nacional",
                uf="BR",
            )
        )

    # 3. Seed DimTipoIndice
    tipos = [
        {"tipo_id": 1, "sigla": "INCC-M", "fonte": "BCB SGS"},
        {"tipo_id": 2, "sigla": "INCC-DI", "fonte": "BCB SGS"},
    ]
    for tipo in tipos:
        existente = session.execute(
            select(DimTipoIndice).where(DimTipoIndice.tipo_id == tipo["tipo_id"])
        ).scalar_one_or_none()
        if not existente:
            session.add(
                DimTipoIndice(
                    tipo_id=tipo["tipo_id"],
                    sigla=tipo["sigla"],
                    fonte=tipo["fonte"],
                )
            )

    session.commit()
    logger.info("Default dimensions verified/seeded successfully.")


def init_db() -> None:
    """Creates all database tables defined in metadata and seeds baseline dimensions."""
    logger.info("Initializing database schema...")
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        seed_default_dimensions(session)
    logger.info("Database schema initialized.")
