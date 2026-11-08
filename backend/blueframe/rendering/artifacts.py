from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Callable
from uuid import uuid4

from pydantic import Field
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from blueframe.domain.common import DomainModel


class RenderArtifact(DomainModel):
    id: str
    job_id: str
    project_id: str
    plan_id: str
    spec_hash: str
    status: str
    working_path: Path
    published_path: Path | None = None
    checksum: str | None = None
    created_at: datetime
    updated_at: datetime


class RenderArtifactRepository:
    def __init__(
        self, session_factory: sessionmaker[Session],
        *, clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock

    def find_completed(self, project_id: str, plan_id: str, spec_hash: str) -> RenderArtifact | None:
        with self._session_factory() as session:
            row = session.execute(text(
                """SELECT * FROM render_artifacts WHERE project_id=:project AND plan_id=:plan
                AND spec_hash=:hash AND status='completed' ORDER BY created_at DESC LIMIT 1"""
            ), {"project": project_id, "plan": plan_id, "hash": spec_hash}).mappings().first()
            return None if row is None else self._model(row)

    def start(self, *, job_id: str, project_id: str, plan_id: str, spec_hash: str, working_path: Path) -> RenderArtifact:
        now = self._clock(); artifact_id = str(uuid4())
        with self._session_factory.begin() as session:
            session.execute(text(
                """INSERT INTO render_artifacts
                (id,job_id,project_id,plan_id,spec_hash,status,working_path,created_at,updated_at)
                VALUES (:id,:job,:project,:plan,:hash,'rendering',:work,:now,:now)"""
            ), {"id": artifact_id, "job": job_id, "project": project_id, "plan": plan_id,
                "hash": spec_hash, "work": str(working_path), "now": now.isoformat()})
        return RenderArtifact(id=artifact_id, job_id=job_id, project_id=project_id, plan_id=plan_id,
                              spec_hash=spec_hash, status="rendering", working_path=working_path,
                              created_at=now, updated_at=now)

    def update(self, artifact_id: str, *, status: str, published_path: Path | None = None, checksum: str | None = None) -> RenderArtifact:
        now = self._clock()
        with self._session_factory.begin() as session:
            session.execute(text(
                """UPDATE render_artifacts SET status=:status,published_path=:published,
                checksum=:checksum,updated_at=:now WHERE id=:id"""
            ), {"status": status, "published": None if published_path is None else str(published_path),
                "checksum": checksum, "now": now.isoformat(), "id": artifact_id})
            row = session.execute(text("SELECT * FROM render_artifacts WHERE id=:id"), {"id": artifact_id}).mappings().one()
            return self._model(row)

    @staticmethod
    def _model(row) -> RenderArtifact:
        def date(value): return datetime.fromisoformat(value) if isinstance(value, str) else value.replace(tzinfo=value.tzinfo or UTC)
        return RenderArtifact(
            id=row.id, job_id=row.job_id, project_id=row.project_id, plan_id=row.plan_id,
            spec_hash=row.spec_hash, status=row.status, working_path=Path(row.working_path),
            published_path=Path(row.published_path) if row.published_path else None,
            checksum=row.checksum, created_at=date(row.created_at), updated_at=date(row.updated_at),
        )
