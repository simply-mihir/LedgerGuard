"""FastAPI application factory for LedgerGuard services."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ledgerguard.api.auth_routes import auth_router
from ledgerguard.api.routes import router
from ledgerguard.db.pool import close_all_pools


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and clean shutdown of database pools."""
    yield
    close_all_pools()


def create_app() -> FastAPI:
    """Create and configure the FastAPI LedgerGuard application."""
    app = FastAPI(
        title="LedgerGuard API",
        description="Financial ledger with verifiable accounting and recoverable transfers",
        version="1.0.0",
        lifespan=lifespan,
    )

    trusted_origins = [
        "http://localhost:3300",
        "http://127.0.0.1:3300",
        "http://localhost:8010",
        "http://127.0.0.1:8010",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=trusted_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["System"])
    def health_check() -> dict[str, str]:
        return {"status": "UP", "version": "1.0.0"}

    app.include_router(auth_router)
    app.include_router(router)
    return app


app = create_app()
