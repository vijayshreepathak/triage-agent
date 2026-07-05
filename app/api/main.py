"""Application entrypoint: ``uvicorn app.api.main:app``.

App factory pattern so tests can build isolated instances. The global
exception handler is the final line of the "never return raw exceptions"
guarantee: anything that escapes the graph's own containment becomes a
uniform, user-safe 500 envelope with the request ID for correlation.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.middleware import RateLimitMiddleware, RequestContextMiddleware
from app.api.routes import router
from app.config.settings import get_settings
from app.schemas.triage import ErrorResponse
from app.utils.logging import configure_logging, get_logger, request_id_var

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

logger = get_logger(__name__)


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info(
        "application starting",
        extra={
            "llm_provider": str(settings.llm_provider),
            "search_provider": str(settings.search_provider),
            "auth_mode": settings.auth_mode,
            "env": settings.app_env,
        },
    )
    # Initialize persistence (idempotent) — local import keeps module import cheap.
    from app.api.deps import get_database

    database = get_database()
    await database.create_all()
    if settings.auth_mode == "clerk" and not settings.clerk_configured:
        logger.warning(
            "AUTH_MODE=clerk but Clerk is not fully configured — "
            "set CLERK_PUBLISHABLE_KEY and CLERK_ISSUER (or CLERK_JWKS_URL)"
        )
    yield
    await database.dispose()
    logger.info("application shutting down")


def create_app() -> FastAPI:
    """Build the FastAPI application with middleware and error handling."""
    settings = get_settings()
    app = FastAPI(
        title="Symptom Triage Agent",
        version="2.0.0",
        description="Clinical triage backend — FastAPI + LangGraph + Pydantic v2.",
        lifespan=_lifespan,
    )
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    # Middleware runs bottom-up: request context first, then rate limiting.
    app.add_middleware(RateLimitMiddleware, requests_per_minute=settings.rate_limit_per_minute)
    app.add_middleware(RequestContextMiddleware)
    # Legacy static assets only in dev — production serves API-only at /.
    if settings.app_env.strip().lower() != "production":
        app.mount("/assets", StaticFiles(directory=_STATIC_DIR), name="assets")
    app.include_router(router)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        # Root cause goes to logs; the client gets a safe envelope only.
        logger.error("unhandled exception", extra={"error": repr(exc)}, exc_info=True)
        payload = ErrorResponse(
            error="internal_error",
            request_id=request_id_var.get(),
            detail="An internal error occurred. If this is a medical emergency, call emergency services.",
        )
        return JSONResponse(status_code=500, content=payload.model_dump())

    return app


app = create_app()
