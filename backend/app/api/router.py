"""Central API router registry for TraceGuard."""

from fastapi import APIRouter

from backend.app.api.actions import router as actions_router
from backend.app.api.health import router as health_router
from backend.app.api.incidents import router as incidents_router
from backend.app.api.integrity import router as integrity_router
from backend.app.api.webhooks import router as webhooks_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(webhooks_router)
api_router.include_router(integrity_router)
api_router.include_router(incidents_router)
api_router.include_router(actions_router)
