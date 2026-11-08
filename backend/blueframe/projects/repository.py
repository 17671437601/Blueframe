from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Iterable
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from blueframe.projects.models import (
    Project,
    ProjectConfigSnapshot,
    ProjectSource,
    ProjectStatus,
    ProjectType,
    SourceRegistration,
)


class ProjectRepository:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock

    def create(
        self,
        *,
        name: str,
        project_type: ProjectType,
        root_path: Path,
        output_relative_path: str,
        config: dict,
        idempotency_key: str,
    ) -> Project:
        now = self._clock()
        with self._session_factory.begin() as session:
            existing = session.execute(
                text("SELECT * FROM projects WHERE idempotency_key=:key"),
                {"key": idempotency_key},
            ).mappings().first()
            if existing is not None:
                return _project(existing)
            project_id = str(uuid4())
            session.execute(
                text(
                    """INSERT INTO projects
                    (id, name, project_type, status, root_path,
                     output_relative_path, config_version, config_json,
                     idempotency_key, created_at, updated_at)
                    VALUES (:id, :name, :type, 'draft', :root, :output, 1,
                            :config, :key, :now, :now)"""
                ),
                {
                    "id": project_id,
                    "name": name.strip(),
                    "type": project_type.value,
                    "root": str(root_path.resolve()),
                    "output": output_relative_path.replace("\\", "/"),
                    "config": json.dumps(config, ensure_ascii=False, sort_keys=True),
                    "key": idempotency_key,
                    "now": now.isoformat(),
                },
            )
            row = session.execute(
                text("SELECT * FROM projects WHERE id=:id"), {"id": project_id}
            ).mappings().one()
            return _project(row)

    def get(self, project_id: str) -> Project | None:
        with self._session_factory() as session:
            row = session.execute(
                text("SELECT * FROM projects WHERE id=:id"), {"id": project_id}
            ).mappings().first()
            return None if row is None else _project(row)

    def list(self) -> list[Project]:
        with self._session_factory() as session:
            rows = session.execute(
                text("SELECT * FROM projects ORDER BY updated_at DESC, created_at DESC")
            ).mappings().all()
            return [_project(row) for row in rows]

    def add_sources(
        self, project_id: str, registrations: Iterable[SourceRegistration]
    ) -> list[ProjectSource]:
        now = self._clock()
        results: list[ProjectSource] = []
        with self._session_factory.begin() as session:
            if session.execute(
                text("SELECT 1 FROM projects WHERE id=:id"), {"id": project_id}
            ).first() is None:
                raise KeyError(project_id)
            next_order = int(
                session.execute(
                    text(
                        "SELECT COALESCE(MAX(order_index), -1) + 1 "
                        "FROM project_sources WHERE project_id=:id"
                    ),
                    {"id": project_id},
                ).scalar_one()
            )
            for registration in registrations:
                existing = session.execute(
                    text(
                        """SELECT * FROM project_sources
                        WHERE project_id=:project_id AND relative_path=:path
                          AND content_fingerprint=:fingerprint"""
                    ),
                    {
                        "project_id": project_id,
                        "path": registration.relative_path,
                        "fingerprint": registration.content_fingerprint,
                    },
                ).mappings().first()
                if existing is not None:
                    results.append(_source(existing))
                    continue
                source_id = str(uuid4())
                session.execute(
                    text(
                        """INSERT INTO project_sources
                        (id, project_id, relative_path, order_index, size_bytes,
                         modified_ns, content_fingerprint, media_info_json,
                         created_at, updated_at)
                        VALUES (:id, :project_id, :path, :order_index, :size,
                                :modified, :fingerprint, NULL, :now, :now)"""
                    ),
                    {
                        "id": source_id,
                        "project_id": project_id,
                        "path": registration.relative_path,
                        "order_index": next_order,
                        "size": registration.size_bytes,
                        "modified": registration.modified_ns,
                        "fingerprint": registration.content_fingerprint,
                        "now": now.isoformat(),
                    },
                )
                row = session.execute(
                    text("SELECT * FROM project_sources WHERE id=:id"),
                    {"id": source_id},
                ).mappings().one()
                results.append(_source(row))
                next_order += 1
            session.execute(
                text("UPDATE projects SET updated_at=:now WHERE id=:id"),
                {"now": now.isoformat(), "id": project_id},
            )
        return results

    def list_sources(self, project_id: str) -> list[ProjectSource]:
        with self._session_factory() as session:
            rows = session.execute(
                text(
                    "SELECT * FROM project_sources WHERE project_id=:id "
                    "ORDER BY order_index ASC"
                ),
                {"id": project_id},
            ).mappings().all()
            return [_source(row) for row in rows]

    def get_source(self, source_id: str) -> ProjectSource | None:
        with self._session_factory() as session:
            row = session.execute(
                text("SELECT * FROM project_sources WHERE id=:id"), {"id": source_id}
            ).mappings().first()
            return None if row is None else _source(row)

    def update_media_info(self, source_id: str, media_info: dict) -> ProjectSource:
        now = self._clock()
        with self._session_factory.begin() as session:
            result = session.execute(
                text(
                    "UPDATE project_sources SET media_info_json=:info, updated_at=:now "
                    "WHERE id=:id"
                ),
                {
                    "id": source_id,
                    "info": json.dumps(media_info, ensure_ascii=False, sort_keys=True),
                    "now": now.isoformat(),
                },
            )
            if result.rowcount != 1:
                raise KeyError(source_id)
            row = session.execute(
                text("SELECT * FROM project_sources WHERE id=:id"), {"id": source_id}
            ).mappings().one()
            return _source(row)


def _project(row) -> Project:
    return Project(
        id=row.id,
        name=row.name,
        project_type=row.project_type,
        status=row.status,
        root_path=Path(row.root_path),
        output_relative_path=row.output_relative_path,
        config=ProjectConfigSnapshot(
            version=row.config_version, values=json.loads(row.config_json)
        ),
        idempotency_key=row.idempotency_key,
        created_at=_as_datetime(row.created_at),
        updated_at=_as_datetime(row.updated_at),
    )


def _source(row) -> ProjectSource:
    return ProjectSource(
        id=row.id,
        project_id=row.project_id,
        relative_path=row.relative_path,
        order_index=row.order_index,
        size_bytes=row.size_bytes,
        modified_ns=row.modified_ns,
        content_fingerprint=row.content_fingerprint,
        media_info=None if row.media_info_json is None else json.loads(row.media_info_json),
        created_at=_as_datetime(row.created_at),
        updated_at=_as_datetime(row.updated_at),
    )


def _as_datetime(value: datetime | str) -> datetime:
    return value if isinstance(value, datetime) else datetime.fromisoformat(value)
