"""FastAPI application factory for LedgerGuard services."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["System"])
    def health_check() -> dict[str, str]:
        return {"status": "UP", "version": "1.0.0"}

    app.include_router(router)
    return app


app = create_app()
