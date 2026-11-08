from __future__ import annotations

from datetime import UTC, datetime
from typing import Callable, Sequence
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from blueframe.asr.models import AsrDocument, AsrLine, AsrStatus, EngineSegment


class AsrRepository:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock

    def get_by_cache_key(self, cache_key: str) -> AsrDocument | None:
        with self._session_factory() as session:
            row = session.execute(
                text("SELECT * FROM asr_documents WHERE cache_key=:key"),
                {"key": cache_key},
            ).mappings().first()
            return None if row is None else self._document(session, row)

    def list_for_project(self, project_id: str) -> list[AsrDocument]:
        with self._session_factory() as session:
            rows = session.execute(
                text(
                    """SELECT documents.* FROM asr_documents documents
                    JOIN project_sources sources ON sources.id=documents.source_id
                    WHERE sources.project_id=:project
                    ORDER BY sources.order_index"""
                ),
                {"project": project_id},
            ).mappings().all()
            return [self._document(session, row) for row in rows]

    def save(
        self,
        *,
        source_id: str,
        cache_key: str,
        model_version: str,
        language: str,
        duration_ms: int,
        status: AsrStatus,
        segments: Sequence[EngineSegment] = (),
    ) -> AsrDocument:
        existing = self.get_by_cache_key(cache_key)
        if existing is not None:
            return existing
        document_id = str(uuid4())
        now = self._clock()
        lines = tuple(
            AsrLine(
                index=index,
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
                text=segment.text.strip(),
            )
            for index, segment in enumerate(segments)
            if segment.text.strip()
        )
        document = AsrDocument(
            id=document_id,
            source_id=source_id,
            cache_key=cache_key,
            model_version=model_version,
            language=language,
            duration_ms=duration_ms,
            status=status,
            lines=lines,
        )
        try:
            with self._session_factory.begin() as session:
                session.execute(
                    text(
                        """INSERT INTO asr_documents
                        (id, source_id, cache_key, model_version, language,
                         status, duration_ms, created_at)
                        VALUES (:id, :source, :key, :model, :language,
                                :status, :duration, :created)"""
                    ),
                    {
                        "id": document.id,
                        "source": source_id,
                        "key": cache_key,
                        "model": model_version,
                        "language": language,
                        "status": status.value,
                        "duration": duration_ms,
                        "created": now.isoformat(),
                    },
                )
                for line in document.lines:
                    session.execute(
                        text(
                            """INSERT INTO asr_lines
                            (document_id, line_index, start_ms, end_ms, text)
                            VALUES (:document, :index, :start, :end, :text)"""
                        ),
                        {
                            "document": document.id,
                            "index": line.index,
                            "start": line.start_ms,
                            "end": line.end_ms,
                            "text": line.text,
                        },
                    )
        except IntegrityError:
            existing = self.get_by_cache_key(cache_key)
            if existing is not None:
                return existing
            raise
        return document

    def _document(self, session: Session, row) -> AsrDocument:
        line_rows = session.execute(
            text(
                "SELECT * FROM asr_lines WHERE document_id=:id ORDER BY line_index"
            ),
            {"id": row.id},
        ).mappings().all()
        return AsrDocument(
            id=row.id,
            source_id=row.source_id,
            cache_key=row.cache_key,
            model_version=row.model_version,
            language=row.language,
            duration_ms=row.duration_ms,
            status=row.status,
            lines=tuple(
                AsrLine(
                    index=line.line_index,
                    start_ms=line.start_ms,
                    end_ms=line.end_ms,
                    text=line.text,
                )
                for line in line_rows
            ),
        )
