"""Security and authentication utilities for TraceGuard.

Simple, secure admin authentication protecting dashboard approvals and remediations.
"""

from fastapi import Header, HTTPException, status

from backend.app.core.config import settings


def verify_admin_auth(
    x_admin_token: str | None = Header(None, alias="X-Admin-Token"),
    authorization: str | None = Header(None, alias="Authorization"),
) -> str:
    """Verify admin credentials via X-Admin-Token header or Bearer authorization header.

    Raises HTTP 401 Unauthorized if the credentials do not match ADMIN_PASSWORD.
    """
    token = x_admin_token

    if not token and authorization:
        parts = authorization.strip().split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
        else:
            token = parts[0]

    expected = settings.ADMIN_PASSWORD
    if not token or token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required: invalid or missing credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return "admin"
