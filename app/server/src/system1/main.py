import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import Engine
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import Scope

from system1.agent.router import router as agent_router
from system1.auth.deps import get_principal
from system1.auth.principal import Principal
from system1.auth.verifier import ClerkVerifier, RejectAllVerifier, TokenVerifier
from system1.batch.router import router as batch_router
from system1.config import get_settings
from system1.context.router import router as context_router
from system1.datasets.router import router as datasets_router
from system1.db import init_db, make_engine
from system1.decisions.router import router as decisions_router
from system1.drafting.router import router as drafting_router
from system1.errors import install_error_handlers
from system1.gateway.router_app import router as gateway_router
from system1.gateway.router_public import router as public_router
from system1.generation.router import router as generation_router
from system1.ingest.router import router as ingest_router
from system1.jobs.router import router as jobs_router
from system1.jobs.service import fail_unfinished_jobs
from system1.projects.router import router as projects_router
from system1.providers import Providers, build_providers, get_providers
from system1.registry.router import router as registry_router
from system1.report.router import router as report_router


class ConfigOut(BaseModel):
    sys1_available: bool
    # True when sys1 answers with each project's own live model, so a project without one can't use it yet.
    sys1_needs_live_model: bool = False


log = logging.getLogger(__name__)


class ClientFiles(StaticFiles):
    """The built client. A path that isn't a file gets index.html, so the client's router can handle deep links."""

    async def get_response(self, path: str, scope: Scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            # An unknown API path should stay a 404, not turn into the app's HTML.
            if exc.status_code != 404 or path.split("/")[0] in ("api", "v1"):
                raise
            return await super().get_response("index.html", scope)


def create_app(
    verifier: TokenVerifier | None = None, engine: Engine | None = None, providers: Providers | None = None
) -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        init_db(app.state.engine)
        fail_unfinished_jobs(app.state.engine)
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

    @api.get("/config", dependencies=[Depends(get_principal)])
    def config(providers: Annotated[Providers, Depends(get_providers)]) -> ConfigOut:
        return ConfigOut(
            sys1_available=providers.sys1 is not None,
            sys1_needs_live_model=getattr(providers.sys1, "serves_adapters", False),
        )

    api.include_router(projects_router)
    api.include_router(context_router)
    api.include_router(datasets_router)
    api.include_router(ingest_router)
    api.include_router(gateway_router)
    api.include_router(decisions_router)
    api.include_router(agent_router)
    api.include_router(generation_router)
    api.include_router(jobs_router)
    api.include_router(drafting_router)
    api.include_router(report_router)
    api.include_router(registry_router)
    api.include_router(batch_router)
    app.include_router(api)
    app.include_router(public_router)
    # Mounted last so every API route matches first. In development Vite serves the client instead.
    if settings.static_dir:
        app.mount("/", ClientFiles(directory=settings.static_dir, html=True), name="client")
    return app


app = create_app()
