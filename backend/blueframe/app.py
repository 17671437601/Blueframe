from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from sqlalchemy import text

from blueframe.config import Settings
from blueframe.db.engine import create_engine_and_session


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine, session_factory = create_engine_and_session(resolved_settings)
        app.state.settings = resolved_settings
        app.state.engine = engine
        app.state.session_factory = session_factory
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(title="BlueFrame Local API", version="0.1.0", lifespan=lifespan)

    @app.get("/health", include_in_schema=False)
    def health() -> dict[str, str]:
        with app.state.session_factory() as session:
            session.execute(text("SELECT 1"))
        return {"status": "ok", "database": "ok"}

    return app
