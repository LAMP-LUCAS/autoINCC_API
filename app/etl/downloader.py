"""Downloader module for extracting INCC time series from Central Bank of Brazil (BCB SGS).

Consumes public series:
- Series 192: INCC-M (Índice Nacional de Custo da Construção - Mercado)
- Series 7456: INCC-DI (Índice Nacional de Custo da Construção - Disponibilidade Interna)
"""

from datetime import date
from typing import Any, Dict, List, Optional
import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from app.core.config import settings
from app.core.logging import get_logger
from app.etl.pacing import RequestPacer

logger = get_logger(__name__)

SERIES_MAP = {
    192: {"sigla": "INCC-M", "tipo_id": 1},
    7456: {"sigla": "INCC-DI", "tipo_id": 2},
}


class BCBDownloader:
    """Downloader for BCB SGS economic time series with polite pacing, retry logic, and error handling."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: int = 30,
        pacer: Optional[RequestPacer] = None,
    ) -> None:
        """Initializes the BCBDownloader.

        Args:
            base_url (Optional[str]): Base endpoint for SGS API. If None, uses config.
            timeout (int): HTTP request timeout in seconds.
            pacer (Optional[RequestPacer]): Pacer instance for rate limiting and jitter.
        """
        self.base_url = (base_url or settings.BCB_API_URL).rstrip("/")
        self.timeout = timeout
        self.pacer = pacer or RequestPacer()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/128.0.0.0 Safari/537.36 "
                    "(AutoINCC-Bot/1.0; +https://github.com/LAMP-LUCAS/autoINCC_API)"
                ),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            }
        )

    @retry(
        reraise=True,
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.RequestException, ConnectionError, TimeoutError)),
        before_sleep=before_sleep_log(logger, 20),
    )
    def fetch_series_raw(
        self,
        serie_codigo: int,
        data_inicial: Optional[date] = None,
        data_final: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """Downloads raw JSON observations from BCB SGS for a given series code with polite pacing.

        Args:
            serie_codigo (int): BCB series numerical code (e.g. 192 or 7456).
            data_inicial (Optional[date]): Starting filter date (inclusive).
            data_final (Optional[date]): Ending filter date (inclusive).

        Returns:
            List[Dict[str, Any]]: List of records [{'data': 'DD/MM/YYYY', 'valor': 'X.XX'}, ...].

        Raises:
            requests.HTTPError: If server responds with 4xx or 5xx.
            ValueError: If series code is not supported or returned payload is invalid.
        """
        # Apply polite pacing with stochastic jitter before issuing request
        self.pacer.pace(target_label=f"BCB SGS serie {serie_codigo}")

        url = f"{self.base_url}.{serie_codigo}/dados"
        params: Dict[str, str] = {"formato": "json"}

        if data_inicial:
            params["dataInicial"] = data_inicial.strftime("%d/%m/%Y")
        if data_final:
            params["dataFinal"] = data_final.strftime("%d/%m/%Y")

        logger.info(
            "Fetching series %s from BCB SGS (url=%s, params=%s)",
            serie_codigo,
            url,
            params,
        )

        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()

        data = response.json()
        if not isinstance(data, list):
            raise ValueError(f"Unexpected JSON structure from BCB SGS for series {serie_codigo}: {data}")

        logger.info(
            "Successfully fetched %d records for series %s from BCB SGS",
            len(data),
            serie_codigo,
        )
        return data

    def download_all_configured_series(
        self,
        data_inicial: Optional[date] = None,
        data_final: Optional[date] = None,
    ) -> Dict[int, List[Dict[str, Any]]]:
        """Downloads all mapped series (192 and 7456).

        Args:
            data_inicial (Optional[date]): Starting filter date.
            data_final (Optional[date]): Ending filter date.

        Returns:
            Dict[int, List[Dict[str, Any]]]: Dictionary mapping serie_codigo to raw records.
        """
        results = {}
        for serie_code in SERIES_MAP.keys():
            try:
                results[serie_code] = self.fetch_series_raw(
                    serie_codigo=serie_code,
                    data_inicial=data_inicial,
                    data_final=data_final,
                )
            except Exception as e:
                logger.error("Failed to download series %s: %s", serie_code, e, exc_info=True)
                raise
        return results
