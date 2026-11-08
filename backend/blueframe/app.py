from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator
import hmac
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text

from blueframe.config import Settings
from blueframe.db.engine import create_engine_and_session
from blueframe.api.dependencies import session_dependency
from blueframe.api.routes.account import build_account_router
from blueframe.api.routes.analysis import build_analysis_router
from blueframe.api.routes.edit_plans import build_edit_plan_router
from blueframe.api.routes.jobs import build_jobs_router
from blueframe.api.routes.projects import build_projects_router
from blueframe.api.routes.providers import build_provider_router
from blueframe.api.routes.system import build_system_router
from blueframe.security.session_token import SessionTokenVerifier, generate_session_token


class RegisterRootRequest(BaseModel):
    root_path: str


def create_app(
    settings: Settings | None = None,
    *,
    session_token: str | None = None,
    job_repository=None,
    account_service=None,
    project_repository=None,
    project_path_registry=None,
    media_probe=None,
    bridge_secret: str | None = None,
    provider_config_service=None,
    analysis_repository=None,
    edit_plan_repository=None,
    open_path=None,
) -> FastAPI:
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

    verifier = SessionTokenVerifier(session_token or generate_session_token())
    require_session = session_dependency(verifier)
    app.include_router(build_system_router(require_session), prefix="/api/v1")
    if provider_config_service is not None:
        app.include_router(
            build_provider_router(require_session, provider_config_service),
            prefix="/api/v1",
        )
    if account_service is not None:
        app.include_router(
            build_account_router(require_session, account_service), prefix="/api/v1"
        )
    if job_repository is not None and account_service is not None:
        app.include_router(
            build_jobs_router(require_session, job_repository, account_service),
            prefix="/api/v1",
        )

    if bridge_secret is not None and project_path_registry is not None:
        @app.post(
            "/internal/project-roots",
            status_code=status.HTTP_201_CREATED,
            include_in_schema=False,
        )
        def register_project_root(
            request: RegisterRootRequest,
            supplied_secret: str | None = Header(None, alias="X-BlueFrame-Bridge"),
        ) -> dict[str, str]:
            if supplied_secret is None or not hmac.compare_digest(
                supplied_secret, bridge_secret
            ):
                raise HTTPException(401, detail="bridge authentication required")
            try:
                root_id = project_path_registry.register(Path(request.root_path))
            except (OSError, ValueError):
                raise HTTPException(400, detail="invalid project root")
            return {"root_id": root_id}
    if bridge_secret is not None and project_repository is not None and open_path is not None:
        @app.post(
            "/internal/projects/{project_id}/open-output",
            include_in_schema=False,
        )
        def open_project_output(
            project_id: str,
            supplied_secret: str | None = Header(None, alias="X-BlueFrame-Bridge"),
        ) -> dict[str, bool]:
            if supplied_secret is None or not hmac.compare_digest(supplied_secret, bridge_secret):
                raise HTTPException(401, detail="bridge authentication required")
            project = project_repository.get(project_id)
            if project is None:
                raise HTTPException(404, detail="project not found")
            from blueframe.security.project_paths import resolve_within_root
            output = resolve_within_root(project.root_path, project.output_relative_path)
            output.mkdir(parents=True, exist_ok=True)
            open_path(output)
            return {"opened": True}
    if all(
        dependency is not None
        for dependency in (
            project_repository,
            project_path_registry,
            media_probe,
            job_repository,
            account_service,
        )
    ):
        app.include_router(
            build_projects_router(
                require_session,
                project_repository,
                project_path_registry,
                media_probe,
                job_repository,
                account_service,
            ),
            prefix="/api/v1",
        )
    if all(
        dependency is not None
        for dependency in (
            project_repository,
            edit_plan_repository,
            job_repository,
            account_service,
        )
    ):
        app.include_router(
            build_edit_plan_router(
                require_session, project_repository, edit_plan_repository,
                job_repository, account_service,
            ),
            prefix="/api/v1",
        )
    if all(
        dependency is not None
        for dependency in (
            project_repository,
            job_repository,
            analysis_repository,
            account_service,
            provider_config_service,
        )
    ):
        app.include_router(
            build_analysis_router(
                require_session,
                project_repository,
                job_repository,
                analysis_repository,
                account_service,
                provider_config_service,
                edit_plan_repository,
            ),
            prefix="/api/v1",
        )

    return app
