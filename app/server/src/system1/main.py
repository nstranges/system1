import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine

from system1.auth.deps import get_principal
from system1.auth.principal import Principal
from system1.auth.verifier import ClerkVerifier, RejectAllVerifier, TokenVerifier
from system1.config import get_settings
from system1.db import init_db, make_engine
from system1.errors import install_error_handlers
from system1.gateway.router_app import router as gateway_router
from system1.projects.router import router as projects_router
from system1.providers import Providers, build_providers

log = logging.getLogger(__name__)


def create_app(
    verifier: TokenVerifier | None = None, engine: Engine | None = None, providers: Providers | None = None
) -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        init_db(app.state.engine)
        if app.state.providers is None:
            app.state.providers = build_providers(settings)
        yield

    app = FastAPI(title="system1", lifespan=lifespan)
    app.state.engine = engine or make_engine(settings.database_url)
    if verifier is None:
        if settings.clerk_secret_key:
            verifier = ClerkVerifier(
                settings.clerk_secret_key, settings.client_origins if settings.clerk_enforce_azp else None
            )
        else:
            log.warning("CLERK_SECRET_KEY is not set: every /api request except /api/health will be rejected")
            verifier = RejectAllVerifier()
    app.state.verifier = verifier
    app.state.providers = providers

    install_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.client_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api = APIRouter(prefix="/api")

    @api.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @api.get("/me")
    def me(principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
        return principal

    api.include_router(projects_router)
    api.include_router(gateway_router)
    app.include_router(api)
    return app


app = create_app()
