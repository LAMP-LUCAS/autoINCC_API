import asyncio
import logging
import uuid
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx

from autoincc_mcp.config import get_config
from autoincc_mcp.resolver import resolve_resource

logger = logging.getLogger(__name__)


class APIError(Exception):
    pass


class AuthError(APIError):
    pass


class ForbiddenError(APIError):
    pass


class NotFoundError(APIError):
    pass


class RateLimitError(APIError):
    def __init__(self, message: str, retry_after: float = 5):
        super().__init__(message)
        self.retry_after = retry_after


def retry_delay(response: httpx.Response) -> float:
    value = response.headers.get("Retry-After", "5")
    try:
        return max(0, int(value))
    except ValueError:
        try:
            when = parsedate_to_datetime(value)
            return max(0, (when - datetime.now(UTC)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return 5


class APIClient:
    RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})

    def __init__(self):
        config = get_config()
        self._timeout = config.timeout
        self._max_retries = config.retries
        self._client = httpx.AsyncClient(
            base_url=config.base_url.rstrip("/"),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=httpx.Timeout(config.timeout),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            follow_redirects=False,
            trust_env=False,
        )

    async def get(
        self, path: str, params: dict | None = None, api_key: str | None = None
    ) -> dict | list:
        return await self._request("GET", path, params=params, api_key=api_key)

    async def post(
        self,
        path: str,
        params: dict | None = None,
        json: dict | list | None = None,
        api_key: str | None = None,
    ) -> dict | list:
        return await self._request("POST", path, params=params, json=json, api_key=api_key)

    async def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        json: dict | list | None = None,
        api_key: str | None = None,
    ) -> dict | list:
        for attempt in range(self._max_retries):
            try:
                response = await self._client.request(
                    method,
                    path,
                    params=params,
                    json=json,
                    headers={"X-API-KEY": api_key} if api_key is not None else {},
                )
            except httpx.TransportError as exc:
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(0.5 * (2**attempt))
                    continue
                message = (
                    f"Request timed out after {self._timeout}s"
                    if isinstance(exc, httpx.TimeoutException)
                    else "Gateway connection failed"
                )
                raise APIError(message) from None
            if response.status_code in self.RETRYABLE_STATUSES and attempt < self._max_retries - 1:
                delay = retry_delay(response) if response.status_code == 429 else 0.5 * (2**attempt)
                logger.warning(
                    "Retryable status %d (attempt %d/%d)",
                    response.status_code,
                    attempt + 1,
                    self._max_retries,
                )
                await asyncio.sleep(delay)
                continue
            self._raise_on_error(response, path, str(uuid.uuid4()))
            try:
                result = response.json()
            except ValueError:
                raise APIError("Gateway returned invalid JSON") from None
            if not isinstance(result, (dict, list)):
                raise APIError("Gateway returned an unexpected JSON shape")
            return result
        raise APIError("Gateway request exhausted its attempts")

    @staticmethod
    def _raise_on_error(response: httpx.Response, path: str = "", correlation_id: str = "") -> None:
        status = response.status_code
        suffix = f" [correlation_id={correlation_id}]" if correlation_id else ""
        if status == 401:
            raise AuthError(f"API key ausente ou inválida (header X-API-KEY).{suffix}")
        if status == 402:
            raise APIError(f"Assinatura inativa ou expirada.{suffix}")
        if status == 403:
            raise ForbiddenError(f"Acesso negado ao recurso.{suffix}")
        if status == 404:
            raise NotFoundError(f"{resolve_resource(path)} não encontrado.{suffix}")
        if status == 429:
            delay = retry_delay(response)
            raise RateLimitError(f"Cota excedida. Aguarde {delay:g}s.{suffix}", delay)
        if status >= 300:
            raise APIError(f"Erro {status} na API.{suffix}")

    async def close(self) -> None:
        await self._client.aclose()
