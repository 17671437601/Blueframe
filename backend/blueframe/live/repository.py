from __future__ import annotations

from datetime import UTC, datetime
from typing import Callable
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from blueframe.live.models import LivePlatform, RecordingSegment, RecordingSession


class RecordingRepository:
    def __init__(self, session_factory: sessionmaker[Session], *, concurrency_limit: int = 2, clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._session_factory, self.concurrency_limit, self._clock = session_factory, concurrency_limit, clock

    def create(self, *, project_id: str, platform: LivePlatform, display_name: str, source_reference: str, authorization_confirmed: bool) -> RecordingSession:
        if not authorization_confirmed: raise ValueError("recording authorization confirmation is required")
        platform = LivePlatform(platform)
        now, session_id = self._clock(), str(uuid4())
        with self._session_factory.begin() as session:
            active = int(session.execute(text("SELECT COUNT(*) FROM recording_sessions WHERE intent_active=1" )).scalar_one())
            if active >= self.concurrency_limit: raise RuntimeError("live recording concurrency limit reached")
            session.execute(text("""INSERT INTO recording_sessions
                (id,project_id,platform,display_name,source_reference,authorization_confirmed_at,intent_active,status,process_id,reconnect_count,created_at,updated_at)
                VALUES (:id,:project,:platform,:name,:source,:confirmed,1,'queued',NULL,0,:created,:updated)"""), {
                "id": session_id, "project": project_id, "platform": platform.value, "name": display_name,
                "source": source_reference, "confirmed": now.isoformat(), "created": now.isoformat(), "updated": now.isoformat(),
            })
        return self.get(session_id)

    def get(self, session_id: str) -> RecordingSession | None:
        with self._session_factory() as session:
            row = session.execute(text("SELECT * FROM recording_sessions WHERE id=:id"), {"id": session_id}).mappings().first()
        return None if row is None else self._model(row)

    def list(self, project_id: str | None = None) -> list[RecordingSession]:
        query, values = "SELECT * FROM recording_sessions", {}
        if project_id: query, values = query + " WHERE project_id=:project", {"project": project_id}
        with self._session_factory() as session:
            rows = session.execute(text(query + " ORDER BY created_at DESC"), values).mappings().all()
        return [self._model(row) for row in rows]

    def mark_recording(self, session_id: str, process_id: int | None = None) -> RecordingSession:
        self._update(session_id, status="recording", process_id=process_id)
        return self.get(session_id)

    def mark_reconnecting(self, session_id: str) -> RecordingSession:
        with self._session_factory.begin() as session:
            session.execute(text("""UPDATE recording_sessions SET status='reconnecting',process_id=NULL,
                reconnect_count=reconnect_count+1,updated_at=:updated WHERE id=:id"""), {
                "updated": self._clock().isoformat(), "id": session_id,
            })
        return self.get(session_id)

    def stop_intent(self, session_id: str, *, status: str = "stopped") -> RecordingSession:
        with self._session_factory.begin() as session:
            session.execute(text("UPDATE recording_sessions SET intent_active=0,status=:status,process_id=NULL,updated_at=:updated WHERE id=:id"), {
                "status": status, "updated": self._clock().isoformat(), "id": session_id,
            })
        return self.get(session_id)

    def recover_intents(self) -> list[RecordingSession]:
        with self._session_factory.begin() as session:
            session.execute(text("""UPDATE recording_sessions SET status='interrupted',process_id=NULL,updated_at=:updated
                WHERE intent_active=1 AND status IN ('recording','reconnecting','starting')"""), {"updated": self._clock().isoformat()})
        return [item for item in self.list() if item.intent_active]

    def add_segment(self, *, session_id: str, sequence: int, path) -> RecordingSegment:
        existing = next((item for item in self.list_segments(session_id) if item.sequence == sequence), None)
        if existing is not None: return existing
        now, segment_id = self._clock(), str(uuid4())
        with self._session_factory.begin() as session:
            session.execute(text("""INSERT INTO recording_segments
                (id,session_id,sequence,path,status,size_bytes,duration_ms,created_at,updated_at)
                VALUES (:id,:session,:sequence,:path,'recording',0,0,:created,:updated)"""), {
                "id": segment_id, "session": session_id, "sequence": sequence, "path": str(path),
                "created": now.isoformat(), "updated": now.isoformat(),
            })
        return self.get_segment(segment_id)

    def get_segment(self, segment_id: str) -> RecordingSegment | None:
        with self._session_factory() as session:
            row = session.execute(text("SELECT * FROM recording_segments WHERE id=:id"), {"id": segment_id}).mappings().first()
        return None if row is None else self._segment(row)

    def list_segments(self, session_id: str) -> list[RecordingSegment]:
        with self._session_factory() as session:
            rows = session.execute(text("SELECT * FROM recording_segments WHERE session_id=:session ORDER BY sequence"), {"session": session_id}).mappings().all()
        return [self._segment(row) for row in rows]

    def update_segment(self, segment_id: str, *, status: str, size_bytes: int, duration_ms: int, fingerprint: str | None = None) -> RecordingSegment:
        with self._session_factory.begin() as session:
            session.execute(text("""UPDATE recording_segments SET status=:status,size_bytes=:size,duration_ms=:duration,
                fingerprint=:fingerprint,updated_at=:updated WHERE id=:id"""), {
                "status": status, "size": size_bytes, "duration": duration_ms, "fingerprint": fingerprint,
                "updated": self._clock().isoformat(), "id": segment_id,
            })
        return self.get_segment(segment_id)

    def _update(self, session_id: str, *, status: str, process_id: int | None) -> None:
        with self._session_factory.begin() as session:
            session.execute(text("UPDATE recording_sessions SET status=:status,process_id=:process,updated_at=:updated WHERE id=:id"), {
                "status": status, "process": process_id, "updated": self._clock().isoformat(), "id": session_id,
            })

    @staticmethod
    def _model(row) -> RecordingSession:
        def date(value): return datetime.fromisoformat(value) if isinstance(value, str) else value.replace(tzinfo=value.tzinfo or UTC)
        return RecordingSession(
            id=row.id, project_id=row.project_id, platform=row.platform, display_name=row.display_name,
            source_reference=row.source_reference, authorization_confirmed_at=date(row.authorization_confirmed_at),
            intent_active=bool(row.intent_active), status=row.status, process_id=row.process_id,
            reconnect_count=row.reconnect_count, error_summary=row.error_summary,
            created_at=date(row.created_at), updated_at=date(row.updated_at),
        )

    @staticmethod
    def _segment(row) -> RecordingSegment:
        def date(value): return datetime.fromisoformat(value) if isinstance(value, str) else value.replace(tzinfo=value.tzinfo or UTC)
        return RecordingSegment(
            id=row.id, session_id=row.session_id, sequence=row.sequence, path=row.path,
            status=row.status, size_bytes=row.size_bytes, duration_ms=row.duration_ms,
            fingerprint=row.fingerprint, created_at=date(row.created_at), updated_at=date(row.updated_at),
        )
