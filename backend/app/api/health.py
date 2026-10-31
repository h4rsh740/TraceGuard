"""Health check endpoint for TraceGuard."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.db.session import get_db

router = APIRouter(tags=["Health"])


@router.get("/health", status_code=status.HTTP_200_OK)
def health_check(db: Session = Depends(get_db)) -> dict:
    """System health check verifying API readiness, DB connectivity, and Sandbox mode."""
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {str(e)}"
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "degraded",
                "app": settings.APP_NAME,
                "version": settings.VERSION,
                "database": db_status,
                "sandbox_mode": True,
            },
        ) from e

    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        "database": db_status,
        "sandbox_mode": True,
        "paypal_base_url": settings.PAYPAL_BASE_URL,
    }
