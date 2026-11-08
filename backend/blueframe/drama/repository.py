from __future__ import annotations

from datetime import UTC, datetime
from typing import Callable
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from blueframe.drama.models import StoryAnalysis, StoryAnalysisVersion


class StoryAnalysisRepository:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock

    def save(
        self,
        *,
        project_id: str,
        prompt_version: str,
        provider: str,
        model: str,
        analysis: StoryAnalysis,
    ) -> StoryAnalysisVersion:
        with self._session_factory.begin() as session:
            version = int(
                session.execute(
                    text(
                        "SELECT COALESCE(MAX(version), 0) + 1 "
                        "FROM story_analysis_versions WHERE project_id=:project"
                    ),
                    {"project": project_id},
                ).scalar_one()
            )
            item = StoryAnalysisVersion(
                id=str(uuid4()),
                project_id=project_id,
                version=version,
                prompt_version=prompt_version,
                provider=provider,
                model=model,
                analysis=analysis,
                accepted=False,
                created_at=self._clock(),
            )
            session.execute(
                text(
                    """INSERT INTO story_analysis_versions
                    (id, project_id, version, prompt_version, provider, model,
                     analysis_json, accepted, created_at)
                    VALUES (:id, :project, :version, :prompt, :provider, :model,
                            :analysis, 0, :created)"""
                ),
                {
                    "id": item.id,
                    "project": project_id,
                    "version": version,
                    "prompt": prompt_version,
                    "provider": provider,
                    "model": model,
                    "analysis": analysis.model_dump_json(),
                    "created": item.created_at.isoformat(),
                },
            )
        return item

    def list_for_project(self, project_id: str) -> list[StoryAnalysisVersion]:
        with self._session_factory() as session:
            rows = session.execute(
                text(
                    "SELECT * FROM story_analysis_versions WHERE project_id=:project "
                    "ORDER BY version DESC"
                ),
                {"project": project_id},
            ).mappings().all()
            return [self._model(row) for row in rows]

    def accept(self, *, project_id: str, version: int) -> StoryAnalysisVersion:
        existing = next(
            (item for item in self.list_for_project(project_id) if item.accepted), None
        )
        if existing is not None:
            return existing
        with self._session_factory.begin() as session:
            updated = session.execute(
                text(
                    "UPDATE story_analysis_versions SET accepted=1 "
                    "WHERE project_id=:project AND version=:version"
                ),
                {"project": project_id, "version": version},
            ).rowcount
        if updated != 1:
            raise KeyError("analysis version not found")
        return next(
            item
            for item in self.list_for_project(project_id)
            if item.version == version
        )

    @staticmethod
    def _model(row) -> StoryAnalysisVersion:
        return StoryAnalysisVersion(
            id=row.id,
            project_id=row.project_id,
            version=row.version,
            prompt_version=row.prompt_version,
            provider=row.provider,
            model=row.model,
            analysis=StoryAnalysis.model_validate_json(row.analysis_json),
            accepted=bool(row.accepted),
            created_at=datetime.fromisoformat(row.created_at)
            if isinstance(row.created_at, str)
            else row.created_at.replace(tzinfo=row.created_at.tzinfo or UTC),
        )
