"""FastAPI dependencies for AutoINCC API endpoints."""

from typing import Optional
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: Optional[str] = Security(api_key_header)) -> str:
    """Validates the incoming administrative API key from header `X-API-Key`.

    Args:
        api_key (Optional[str]): Provided API key header value.

    Returns:
        str: Validated API key.

    Raises:
        HTTPException: 403 Forbidden if key is missing or invalid.
    """
    if not api_key or api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Invalid or missing X-API-Key header",
        )
    return api_key


__all__ = ["get_db", "verify_api_key"]
