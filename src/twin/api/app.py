from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from twin.api.repository import Repository
from twin.common.config import Settings, get_settings


def create_app(repository: Repository | None = None, settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = None
        if repository is None:
            from twin.api.db import create_engine, create_session_factory
            from twin.api.sql.repository import SqlRepository

            engine = create_engine(settings.database_url)
            app.state.repository = SqlRepository(create_session_factory(engine))
        yield
        if engine is not None:
            await engine.dispose()

    app = FastAPI(title="DC Digital Twin API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    if repository is not None:
        app.state.repository = repository
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz", tags=["meta"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    from twin.api.routers import fleet, telemetry

    for router_module in (fleet, telemetry):
        app.include_router(router_module.router, prefix="/api")
    return app
