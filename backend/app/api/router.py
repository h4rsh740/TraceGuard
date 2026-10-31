"""Central API router registry for TraceGuard."""

from fastapi import APIRouter

from backend.app.api.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
