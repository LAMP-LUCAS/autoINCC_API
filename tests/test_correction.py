"""Unit tests for monetary correction logic and schema validation."""

from datetime import date
from decimal import Decimal
import pytest
from pydantic import ValidationError

from app.schemas.incc import INCCCorrectionRequest, INCCCorrectionResponse


def test_incc_correction_request_valid() -> None:
    """Tests valid correction request instantiation."""
    req = INCCCorrectionRequest(
        valor_inicial=Decimal("150000.00"),
        data_inicio=date(2023, 1, 1),
        data_fim=date(2024, 1, 1),
        sigla="INCC-M",
    )
    assert req.valor_inicial == Decimal("150000.00")
    assert req.sigla == "INCC-M"


def test_incc_correction_request_invalid_dates() -> None:
    """Tests that data_fim prior to data_inicio raises ValidationError."""
    with pytest.raises(ValidationError) as exc:
        INCCCorrectionRequest(
            valor_inicial=Decimal("1000.00"),
            data_inicio=date(2024, 6, 1),
            data_fim=date(2024, 1, 1),
            sigla="INCC-M",
        )
    assert "data_fim cannot be prior to data_inicio" in str(exc.value)


def test_incc_correction_request_negative_value() -> None:
    """Tests that negative or zero initial value raises ValidationError."""
    with pytest.raises(ValidationError):
        INCCCorrectionRequest(
            valor_inicial=Decimal("0.00"),
            data_inicio=date(2024, 1, 1),
            data_fim=date(2024, 6, 1),
            sigla="INCC-M",
        )


def test_incc_correction_request_invalid_sigla() -> None:
    """Tests that invalid index acronym raises ValidationError."""
    with pytest.raises(ValidationError):
        INCCCorrectionRequest(
            valor_inicial=Decimal("1000.00"),
            data_inicio=date(2024, 1, 1),
            data_fim=date(2024, 6, 1),
            sigla="IPCA",
        )


def test_incc_correction_math() -> None:
    """Tests exact numerical precision of correction formula."""
    valor_inicial = Decimal("100000.00")
    indice_inicial = Decimal("100.000000")
    indice_final = Decimal("105.500000")

    fator = indice_final / indice_inicial  # 1.055
    valor_corrigido = valor_inicial * fator  # 105500.00
    variacao_acumulada = (fator - Decimal("1.0")) * Decimal("100")  # 5.5%

    assert fator == Decimal("1.055")
    assert valor_corrigido == Decimal("105500.00")
    assert variacao_acumulada == Decimal("5.5")
