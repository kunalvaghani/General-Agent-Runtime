"""Application factory shared by the CLI and ASGI servers."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from gar import __version__
from gar.api.routes.health import router
from gar.api.routes.runtime import router as runtime_router
from gar.api.service import RuntimeService
from gar.config import Settings
from gar.logging import configure_logging
from gar.persistence.database import Database


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(config.log_level)
        logger = logging.getLogger("gar.api")
        logger.info("GAR API starting")
        database = Database(config.data_dir / "gar.db")
        try:
            database.initialize()
            app.state.database = database
            app.state.runtime = RuntimeService(database, config)
            yield
        finally:
            if hasattr(app.state, "runtime"):
                await app.state.runtime.close()
            database.close()
            logger.info("GAR API stopped")

    app = FastAPI(title="GAR", version=__version__, lifespan=lifespan)
    app.state.settings = config
    app.include_router(router, prefix="/api/v1")
    app.include_router(runtime_router, prefix="/api/v1")
    origins = [
        str(config.web_origin).rstrip("/"),
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def local_origin(request, call_next):
        if request.headers.get("origin") and request.headers["origin"] not in origins:
            return JSONResponse({"detail": "Origin not allowed"}, status_code=403)
        return await call_next(request)

    return app
