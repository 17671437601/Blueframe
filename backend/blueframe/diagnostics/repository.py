from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker


class DiagnosticsRepository:
    def __init__(self, session_factory: sessionmaker[Session], *, clock=lambda: datetime.now(UTC)) -> None:
        self._session_factory, self._clock = session_factory, clock

    def record(self, *, category: str, stage: str, status: str, duration_ms: int | None = None,
               provider: str | None = None, units: int | None = None, error_code: str | None = None) -> None:
        with self._session_factory.begin() as session:
            session.execute(text("""INSERT INTO diagnostic_metrics
                (id,category,stage,status,duration_ms,provider,units,error_code,created_at)
                VALUES (:id,:category,:stage,:status,:duration,:provider,:units,:error,:created)"""), {
                "id": str(uuid4()), "category": category[:40], "stage": stage[:100], "status": status[:40],
                "duration": duration_ms, "provider": None if provider is None else provider[:80],
                "units": units, "error": None if error_code is None else error_code[:100],
                "created": self._clock().isoformat(),
            })

    def list(self, *, limit: int = 500) -> list[dict]:
        with self._session_factory() as session:
            rows = session.execute(text("""SELECT category,stage,status,duration_ms,provider,units,error_code,created_at
                FROM diagnostic_metrics ORDER BY created_at DESC LIMIT :limit"""), {"limit": max(1, min(limit, 2000))}).mappings().all()
        return [dict(row) for row in rows]
