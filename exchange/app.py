from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import APIRouter, FastAPI

from exchange.config import engine, settings
from exchange.middleware import IdempotencyMiddleware, RequestIdMiddleware
from exchange.models import Base
from exchange.routes import accounts, dashboard, kya_admin, settlement, stats, webhooks
from exchange.schemas import HealthResponse
from exchange.tasks import background_expiry_loop

import exchange.identity.issuer_registry  # noqa: F401 — register TrustedIssuer with Base


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    if settings.auto_create_schema:
        Base.metadata.create_all(bind=engine)

    if settings.kya_enabled:
        from exchange.identity.issuer_registry import IssuerRegistry
        from exchange.config import get_session as _gs

        gen = _gs()
        s = next(gen)
        try:
            with s.begin():
                IssuerRegistry().seed_initial(s)
        finally:
            try:
                next(gen)
            except StopIteration:
                pass

    tasks: list[asyncio.Task] = []
    tasks.append(asyncio.create_task(background_expiry_loop()))

    if settings.kya_enabled:
        from exchange.identity.monitor import KYAMonitor

        kya_monitor = KYAMonitor()
        tasks.append(asyncio.create_task(kya_monitor.run()))

    try:
        yield
    finally:
        for t in tasks:
            t.cancel()
        for t in tasks:
            try:
                await t
            except asyncio.CancelledError:
                pass


def create_app() -> FastAPI:
    app = FastAPI(
        title="A2A Settlement Exchange",
        version="0.9.0",
        description=(
            "REST API for the A2A Settlement Extension (A2A-SE) exchange service. "
            "Provides escrow-based token settlement for the Agent2Agent protocol."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        openapi_tags=[
            {"name": "Health", "description": "Service health check"},
            {"name": "Accounts", "description": "Agent registration, directory, and account management"},
            {"name": "Settlement", "description": "Escrow, release, refund, dispute, and resolve operations"},
            {"name": "Webhooks", "description": "Webhook registration and management"},
            {"name": "Stats", "description": "Network health and statistics"},
        ],
    )

    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(RequestIdMiddleware)

    if settings.settlement_auth_enabled and settings.settlement_auth_key:
        try:
            from a2a_settlement_auth import SettlementMiddleware, SettlementAuthConfig

            auth_config = SettlementAuthConfig(
                verification_key=settings.settlement_auth_key,
                issuer=settings.settlement_auth_issuer or None,
                audience=settings.settlement_auth_audience,
                exempt_paths={
                    "/", "/health", "/docs", "/redoc", "/openapi.json",
                    "/v1/stats", "/api/v1/stats",
                    "/v1/accounts/register", "/api/v1/accounts/register",
                    "/v1/accounts/directory", "/api/v1/accounts/directory",
                },
                exempt_prefixes=[
                    "/.well-known/",
                    "/v1/accounts/",
                    "/api/v1/accounts/",
                    "/v1/dashboard/", "/api/v1/dashboard/",
                    "/v1/agents/", "/api/v1/agents/",
                    "/v1/escrows/", "/api/v1/escrows/",
                    "/v1/disputes/", "/api/v1/disputes/",
                ],
            )
            app.add_middleware(SettlementMiddleware, config=auth_config)
        except ImportError:
            import logging
            logging.getLogger("exchange").warning(
                "A2A_EXCHANGE_SETTLEMENT_AUTH_ENABLED=true but a2a-settlement-auth is not installed"
            )

    @app.get("/health", response_model=HealthResponse, tags=["Health"])
    def health() -> HealthResponse:
        return HealthResponse()

    api_router = APIRouter()
    api_router.include_router(accounts.router)
    api_router.include_router(settlement.router)
    api_router.include_router(stats.router)
    api_router.include_router(webhooks.router)
    api_router.include_router(kya_admin.router)
    api_router.include_router(dashboard.router)

    app.include_router(api_router, prefix="/v1")
    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "exchange.app:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level="info",
    )
