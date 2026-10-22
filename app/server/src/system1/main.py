from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from system1.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="system1")
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

    app.include_router(api)
    return app


app = create_app()
