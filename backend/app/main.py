"""TraceGuard FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.router import api_router
from backend.app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("traceguard")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup validation
    logger.info("Initializing TraceGuard backend...")
    logger.info("PayPal Mode: SANDBOX ONLY (%s)", settings.PAYPAL_BASE_URL)
    if (
        "sandbox" not in settings.PAYPAL_BASE_URL.lower()
        and not settings.PAYPAL_BASE_URL.startswith("http://localhost")
    ):
        logger.critical("Refusing startup: PAYPAL_BASE_URL is not configured for Sandbox!")
        raise RuntimeError("TraceGuard must operate exclusively in PayPal Sandbox.")
    yield
    logger.info("Shutting down TraceGuard backend...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="Flight recorder for PayPal payments: tamper-evident evidence trail, deterministic detection, and human-in-the-loop recovery.",
    lifespan=lifespan,
)

# CORS configuration
origins = [settings.FRONTEND_ORIGIN]
if settings.DEBUG:
    origins.append("http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/")
def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.VERSION,
        "description": "Flight recorder for PayPal payments",
        "docs_url": "/docs",
        "sandbox_mode": True,
    }
