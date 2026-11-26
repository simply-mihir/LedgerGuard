"""FastAPI application factory for LedgerGuard services."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from ledgerguard.api.auth_routes import auth_router
from ledgerguard.api.routes import router
from ledgerguard.db.pool import close_all_pools
from ledgerguard.observability import extract_trace_context, inject_trace_carrier, safe_span


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

    from ledgerguard.config import settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.get_trusted_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def trace_context_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        parent_ctx = extract_trace_context(dict(request.headers))
        with safe_span(
            f"http.{request.method}",
            attributes={"http.method": request.method, "http.route": request.url.path},
            parent_context=parent_ctx,
        ):
            response = await call_next(request)
            carrier = inject_trace_carrier()
            if "traceparent" in carrier:
                response.headers["traceparent"] = carrier["traceparent"]
            return response

    @app.get("/health", tags=["System"])
    def health_check() -> dict[str, str]:
        return {"status": "UP", "version": "1.0.0"}

    app.include_router(auth_router)
    app.include_router(router)
    return app


app = create_app()
