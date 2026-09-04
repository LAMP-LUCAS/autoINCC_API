"""Pytest fixtures and configuration for AutoINCC tests."""

from datetime import date
from decimal import Decimal
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.db.models import Base, DimCategoria, DimGeografia, DimTempo, DimTipoIndice, FatoINCC
from app.db.session import seed_default_dimensions
from app.main import app

# SQLite in-memory configuration for fast unit tests
SQLITE_TEST_URL = "sqlite:///:memory:"

engine_test = create_engine(
    SQLITE_TEST_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database() -> Generator[None, None, None]:
    """Creates database schema and default dimensions once for test session."""
    Base.metadata.create_all(bind=engine_test)
    with TestingSessionLocal() as session:
        seed_default_dimensions(session)
    yield
    Base.metadata.drop_all(bind=engine_test)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Yields an isolated transaction session rolled back after each test."""
    connection = engine_test.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Provides a FastAPI TestClient configured with the overridden test database session."""
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def seeded_incc_data(db_session: Session) -> None:
    """Populates database with sample continuous historical INCC series for testing."""
    # Ensure baseline dimensions
    seed_default_dimensions(db_session)

    # Months: Jan 2024 to Apr 2024
    months = [
        (date(2024, 1, 1), 2024, 1, 1, 1, "Janeiro", Decimal("0.003000"), Decimal("0.003000"), None, Decimal("100.300000")),
        (date(2024, 2, 1), 2024, 2, 1, 1, "Fevereiro", Decimal("0.002000"), Decimal("0.005006"), None, Decimal("100.500600")),
        (date(2024, 3, 1), 2024, 3, 1, 1, "Março", Decimal("0.004000"), Decimal("0.009026"), None, Decimal("100.902602")),
        (date(2024, 4, 1), 2024, 4, 2, 1, "Abril", Decimal("0.005000"), Decimal("0.014071"), None, Decimal("101.407115")),
    ]

    for d_id, ano, mes, tri, sem, nome, v_m, v_ytd, v_12m, num_idx in months:
        tempo = db_session.query(DimTempo).filter_by(data_id=d_id).first()
        if not tempo:
            tempo = DimTempo(data_id=d_id, ano=ano, mes=mes, trimestre=tri, semestre=sem, nome_mes=nome)
            db_session.add(tempo)

        db_session.add(
            FatoINCC(
                data_id=d_id,
                categoria_id=1,
                cidade_id=1,
                tipo_id=1,  # INCC-M
                variacao_mensal=v_m,
                variacao_ytd=v_ytd,
                variacao_12m=v_12m,
                numero_indice=num_idx,
            )
        )

    db_session.commit()


@pytest.fixture
def multi_month_seeded_data(db_session: Session) -> None:
    """Seeds 6 months of historical data for both INCC-M and INCC-DI."""
    seed_default_dimensions(db_session)

    test_data = [
        (date(2024, 1, 1), 2024, 1, 0.50, 0.40),
        (date(2024, 2, 1), 2024, 2, 0.80, 0.70),
        (date(2024, 3, 1), 2024, 3, 1.20, 1.00),
        (date(2024, 4, 1), 2024, 4, 0.60, 0.60),
        (date(2024, 5, 1), 2024, 5, 1.50, 1.40),
        (date(2024, 6, 1), 2024, 6, 0.90, 1.10),
    ]

    idx_m = Decimal("100.0")
    idx_di = Decimal("100.0")

    for d_id, ano, mes, r_m, r_di in test_data:
        tempo = db_session.query(DimTempo).filter_by(data_id=d_id).first()
        if not tempo:
            db_session.add(
                DimTempo(
                    data_id=d_id,
                    ano=ano,
                    mes=mes,
                    trimestre=(mes - 1) // 3 + 1,
                    semestre=1,
                    nome_mes=f"Mês {mes}",
                )
            )

        v_m = Decimal(str(r_m)) / Decimal("100")
        v_di = Decimal(str(r_di)) / Decimal("100")

        idx_m = idx_m * (Decimal("1") + v_m)
        idx_di = idx_di * (Decimal("1") + v_di)

        # INCC-M (tipo_id=1)
        db_session.add(
            FatoINCC(
                data_id=d_id,
                categoria_id=1,
                cidade_id=1,
                tipo_id=1,
                variacao_mensal=v_m,
                variacao_ytd=v_m,
                variacao_12m=None,
                numero_indice=idx_m,
            )
        )

        # INCC-DI (tipo_id=2)
        db_session.add(
            FatoINCC(
                data_id=d_id,
                categoria_id=1,
                cidade_id=1,
                tipo_id=2,
                variacao_mensal=v_di,
                variacao_ytd=v_di,
                variacao_12m=None,
                numero_indice=idx_di,
            )
        )

    db_session.commit()

