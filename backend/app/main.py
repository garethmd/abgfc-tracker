import logging
import sys

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routers import (
    auth,
    club,
    fixtures,
    grounds,
    imports,
    invitations,
    live,
    lookups,
    players,
    reports,
    seasons,
    users,
)
from app.config import get_settings
from app.core.errors import AppError

API_PREFIX = "/api/v1"


def _setup_logging() -> None:
    """Give our own loggers a handler. Uvicorn only configures its own, so without this
    the console email backend writes the invite and sign-in links into the void - and in
    development that log *is* the inbox."""
    log = logging.getLogger("abgfc")
    if not log.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(levelname)s [%(name)s] %(message)s"))
        log.addHandler(handler)
    log.setLevel(logging.INFO)


def create_app() -> FastAPI:
    settings = get_settings()
    _setup_logging()
    app = FastAPI(
        title="ABGFC",
        version="0.1.0",
        # No interactive docs in production: they'd enumerate every endpoint to the internet.
        docs_url=None if settings.is_production else "/api/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/api/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    routers = (
        auth,
        club,
        seasons,
        players,
        lookups,
        fixtures,
        live,
        users,
        reports,
        imports,
        grounds,
        invitations,
    )
    for r in routers:
        app.include_router(r.router, prefix=API_PREFIX)

    @app.get("/api/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
