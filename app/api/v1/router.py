"""Aggregation router for API v1."""

from fastapi import APIRouter
from app.api.v1.incc import router as incc_router
from app.api.v1.etl import router as etl_router

api_v1_router = APIRouter()

api_v1_router.include_router(incc_router)
api_v1_router.include_router(etl_router)

__all__ = ["api_v1_router"]
