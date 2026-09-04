"""SQLAlchemy 2.0 Models representing Star Schema for AutoINCC.

Tables:
- dim_tempo: Temporal dimension
- dim_categoria: Category dimension (e.g. Geral, Materiais, Mão de Obra)
- dim_geografia: Geographic dimension (e.g. Nacional, Capitais)
- dim_tipo_indice: Index variant dimension (e.g. INCC-M, INCC-DI)
- fato_incc: Fact table storing economic rates and calculated continuous index
"""

from datetime import date, datetime
from typing import Optional
from decimal import Decimal

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base declarative model class for SQLAlchemy."""
    pass


class DimTempo(Base):
    """Temporal dimension table for month-level granularities.

    Attributes:
        data_id (date): Primary key, first day of the reference month.
        ano (int): Calendar year (e.g. 2026).
        mes (int): Calendar month (1-12).
        trimestre (int): Quarter of the year (1-4).
        semestre (int): Semester of the year (1-2).
        nome_mes (str): Portuguese month name (e.g. 'Janeiro').
    """

    __tablename__ = "dim_tempo"

    data_id: Mapped[date] = mapped_column(Date, primary_key=True)
    ano: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    mes: Mapped[int] = mapped_column(Integer, nullable=False)
    trimestre: Mapped[int] = mapped_column(Integer, nullable=False)
    semestre: Mapped[int] = mapped_column(Integer, nullable=False)
    nome_mes: Mapped[str] = mapped_column(String(20), nullable=False)

    def __repr__(self) -> str:
        return f"<DimTempo(data_id={self.data_id}, ano={self.ano}, mes={self.mes})>"


class DimCategoria(Base):
    """Category dimension table (e.g. Geral, Materiais e Serviços, Mão de Obra).

    Attributes:
        categoria_id (int): Primary key.
        nome_categoria (str): Name of the category.
        descricao (Optional[str]): Description or details of category composition.
    """

    __tablename__ = "dim_categoria"

    categoria_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome_categoria: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    descricao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<DimCategoria(categoria_id={self.categoria_id}, nome='{self.nome_categoria}')>"


class DimGeografia(Base):
    """Geographical dimension table (e.g. Nacional, São Paulo, Rio de Janeiro).

    Attributes:
        cidade_id (int): Primary key.
        nome_cidade (str): City name or 'Nacional'.
        uf (str): State abbreviation or 'BR'.
    """

    __tablename__ = "dim_geografia"

    cidade_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome_cidade: Mapped[str] = mapped_column(String(100), nullable=False)
    uf: Mapped[str] = mapped_column(String(2), nullable=False)

    def __repr__(self) -> str:
        return f"<DimGeografia(cidade_id={self.cidade_id}, cidade='{self.nome_cidade}', uf='{self.uf}')>"


class DimTipoIndice(Base):
    """Index variation dimension table (e.g. INCC-M, INCC-DI).

    Attributes:
        tipo_id (int): Primary key.
        sigla (str): Unique acronym for the index (e.g. 'INCC-M').
        fonte (str): Primary source provider (e.g. 'BCB SGS', 'FGV IBRE').
    """

    __tablename__ = "dim_tipo_indice"

    tipo_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sigla: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    fonte: Mapped[str] = mapped_column(String(50), nullable=False)

    def __repr__(self) -> str:
        return f"<DimTipoIndice(tipo_id={self.tipo_id}, sigla='{self.sigla}', fonte='{self.fonte}')>"


class FatoINCC(Base):
    """Fact table for INCC monthly observations.

    Stores normalized monthly variation, cumulative year-to-date (YTD),
    12-month rolling variation and calculated base-100 continuous index.

    Composite Primary Key:
        (data_id, categoria_id, cidade_id, tipo_id)
    """

    __tablename__ = "fato_incc"

    data_id: Mapped[date] = mapped_column(
        Date,
        ForeignKey("dim_tempo.data_id", ondelete="CASCADE"),
        primary_key=True,
    )
    categoria_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("dim_categoria.categoria_id", ondelete="CASCADE"),
        primary_key=True,
    )
    cidade_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("dim_geografia.cidade_id", ondelete="CASCADE"),
        primary_key=True,
    )
    tipo_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("dim_tipo_indice.tipo_id", ondelete="CASCADE"),
        primary_key=True,
    )

    variacao_mensal: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=6),
        nullable=False,
        comment="Monthly rate as normalized decimal (e.g. 0.005400 for 0.54%)",
    )
    variacao_ytd: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=10, scale=6),
        nullable=True,
        comment="Year-to-date accumulated variation as decimal",
    )
    variacao_12m: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=10, scale=6),
        nullable=True,
        comment="12-month rolling accumulated variation as decimal",
    )
    numero_indice: Mapped[Decimal] = mapped_column(
        Numeric(precision=28, scale=6),
        nullable=False,
        comment="Base 100 continuous chain index calculated via cumulative product",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    tempo: Mapped["DimTempo"] = relationship("DimTempo", lazy="joined")
    categoria: Mapped["DimCategoria"] = relationship("DimCategoria", lazy="joined")
    geografia: Mapped["DimGeografia"] = relationship("DimGeografia", lazy="joined")
    tipo_indice: Mapped["DimTipoIndice"] = relationship("DimTipoIndice", lazy="joined")

    def __repr__(self) -> str:
        return (
            f"<FatoINCC(data={self.data_id}, tipo_id={self.tipo_id}, "
            f"var_mensal={self.variacao_mensal}, index={self.numero_indice})>"
        )
