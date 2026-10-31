"""TraceGuard core configuration module.

Strictly enforces PayPal Sandbox-only execution and manages environment variables.
"""

from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App Information
    APP_NAME: str = "TraceGuard"
    VERSION: str = "0.1.0"
    DEBUG: bool = False

    # PayPal Sandbox Configuration
    PAYPAL_CLIENT_ID: str = ""
    PAYPAL_CLIENT_SECRET: str = ""
    PAYPAL_WEBHOOK_ID: str = ""
    PAYPAL_BASE_URL: str = "https://api-m.sandbox.paypal.com"

    # LLM Settings (Provider-agnostic)
    LLM_PROVIDER: Literal["openai", "anthropic", "gemini", "mock", ""] = "openai"
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_API_KEY: str = ""

    # Database
    DATABASE_URL: str = "postgresql+psycopg2://traceguard:traceguard@localhost:5432/traceguard_db"

    # Webhook & Host Settings
    PUBLIC_BASE_URL: str = "http://localhost:8000"
    FRONTEND_ORIGIN: str = "http://localhost:3000"

    # Admin Security
    ADMIN_PASSWORD: str = "traceguard_admin_secret"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("PAYPAL_BASE_URL")
    @classmethod
    def validate_sandbox_only(cls, v: str) -> str:
        """Enforce strict sandbox-only rule.

        TraceGuard must NEVER execute or start against live PayPal production endpoints.
        """
        normalized = v.strip().lower()
        if "api-m.paypal.com" in normalized or "api.paypal.com" in normalized:
            raise ValueError(
                "CRITICAL SECURITY VIOLATION: TraceGuard detected live PayPal production URL! "
                "TraceGuard operates strictly in PayPal Sandbox mode (e.g., https://api-m.sandbox.paypal.com). "
                "Startup aborted."
            )
        if "sandbox" not in normalized and not normalized.startswith("http://localhost"):
            raise ValueError(
                f"Invalid PAYPAL_BASE_URL '{v}'. URL must be an official PayPal sandbox URL "
                "(e.g., https://api-m.sandbox.paypal.com)."
            )
        return v.rstrip("/")


settings = Settings()
