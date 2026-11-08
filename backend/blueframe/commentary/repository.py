from __future__ import annotations

from datetime import UTC, datetime
from typing import Callable
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from blueframe.commentary.models import CommentaryScriptVersion, CommentarySentence


class CommentaryRepository:
    def __init__(self, session_factory: sessionmaker[Session], *, clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._session_factory, self._clock = session_factory, clock

    def save(
        self, *, project_id: str, title: str, voice: str, prompt_version: str,
        provider: str, model: str, sentences: tuple[CommentarySentence, ...],
    ) -> CommentaryScriptVersion:
        with self._session_factory.begin() as session:
            version = int(session.execute(text(
                "SELECT COALESCE(MAX(version), 0) + 1 FROM commentary_script_versions WHERE project_id=:project"
            ), {"project": project_id}).scalar_one())
            item = CommentaryScriptVersion(
                id=str(uuid4()), project_id=project_id, version=version, title=title,
                voice=voice, prompt_version=prompt_version, provider=provider, model=model,
                sentences=sentences, created_at=self._clock(),
            )
            session.execute(text("""INSERT INTO commentary_script_versions
                (id, project_id, version, title, voice, prompt_version, provider, model, sentences_json, created_at)
                VALUES (:id, :project, :version, :title, :voice, :prompt, :provider, :model, :sentences, :created)"""), {
                "id": item.id, "project": project_id, "version": version, "title": title,
                "voice": voice, "prompt": prompt_version, "provider": provider, "model": model,
                "sentences": "[" + ",".join(sentence.model_dump_json() for sentence in sentences) + "]",
                "created": item.created_at.isoformat(),
            })
        return item

    def list_for_project(self, project_id: str) -> list[CommentaryScriptVersion]:
        with self._session_factory() as session:
            rows = session.execute(text(
                "SELECT * FROM commentary_script_versions WHERE project_id=:project ORDER BY version DESC"
            ), {"project": project_id}).mappings().all()
        return [self._model(row) for row in rows]

    def get(self, script_id: str) -> CommentaryScriptVersion | None:
        with self._session_factory() as session:
            row = session.execute(text(
                "SELECT * FROM commentary_script_versions WHERE id=:id"
            ), {"id": script_id}).mappings().first()
        return None if row is None else self._model(row)

    @staticmethod
    def _model(row) -> CommentaryScriptVersion:
        import json
        return CommentaryScriptVersion(
            id=row.id, project_id=row.project_id, version=row.version, title=row.title,
            voice=row.voice, prompt_version=row.prompt_version, provider=row.provider,
            model=row.model,
            sentences=tuple(CommentarySentence.model_validate(item) for item in json.loads(row.sentences_json)),
            created_at=datetime.fromisoformat(row.created_at) if isinstance(row.created_at, str)
            else row.created_at.replace(tzinfo=row.created_at.tzinfo or UTC),
        )
