from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Sequence
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from blueframe.story.models import StoryBatch, StoryItem, StoryPlanSpec


class StoryBatchRepository:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._session_factory, self._clock = session_factory, clock

    def create(
        self,
        *,
        project_id: str,
        analysis_version_id: str,
        specs: Sequence[StoryPlanSpec],
        target_count: int,
        min_duration_ms: int,
        max_duration_ms: int,
        burn_subtitles: bool,
    ) -> StoryBatch:
        if not specs:
            raise ValueError("story batch requires at least one plan")
        now, batch_id = self._clock(), str(uuid4())
        with self._session_factory.begin() as session:
            session.execute(
                text(
                    """INSERT INTO story_batches
                    (id,project_id,analysis_version_id,status,target_count,min_duration_ms,
                     max_duration_ms,burn_subtitles,created_at,updated_at)
                    VALUES (:id,:project,:analysis,'queued',:target,:min,:max,:burn,:now,:now)"""
                ),
                {
                    "id": batch_id,
                    "project": project_id,
                    "analysis": analysis_version_id,
                    "target": target_count,
                    "min": min_duration_ms,
                    "max": max_duration_ms,
                    "burn": 1 if burn_subtitles else 0,
                    "now": now.isoformat(),
                },
            )
            for index, spec in enumerate(specs):
                session.execute(
                    text(
                        """INSERT INTO story_items
                        (id,batch_id,item_index,title,target_duration_ms,status)
                        VALUES (:id,:batch,:index,:title,:duration,'queued')"""
                    ),
                    {
                        "id": str(uuid4()),
                        "batch": batch_id,
                        "index": index,
                        "title": spec.title,
                        "duration": spec.target_duration_ms,
                    },
                )
        return self.get(batch_id)

    def get(self, batch_id: str) -> StoryBatch | None:
        with self._session_factory() as session:
            row = session.execute(
                text("SELECT * FROM story_batches WHERE id=:id"), {"id": batch_id}
            ).mappings().first()
            if row is None:
                return None
            items = session.execute(
                text("SELECT * FROM story_items WHERE batch_id=:id ORDER BY item_index"),
                {"id": batch_id},
            ).mappings().all()
        return StoryBatch(
            id=row.id,
            project_id=row.project_id,
            analysis_version_id=row.analysis_version_id,
            status=row.status,
            target_count=row.target_count,
            min_duration_ms=row.min_duration_ms,
            max_duration_ms=row.max_duration_ms,
            burn_subtitles=bool(row.burn_subtitles),
            items=tuple(
                StoryItem(
                    id=item.id,
                    batch_id=item.batch_id,
                    item_index=item.item_index,
                    title=item.title,
                    target_duration_ms=item.target_duration_ms,
                    plan_id=item.plan_id,
                    status=item.status,
                    output_path=Path(item.output_path) if item.output_path else None,
                    error_summary=item.error_summary,
                )
                for item in items
            ),
            created_at=_date(row.created_at),
            updated_at=_date(row.updated_at),
        )

    def list_for_project(self, project_id: str) -> list[StoryBatch]:
        with self._session_factory() as session:
            ids = session.execute(
                text(
                    "SELECT id FROM story_batches WHERE project_id=:project ORDER BY created_at DESC"
                ),
                {"project": project_id},
            ).scalars().all()
        return [batch for batch_id in ids if (batch := self.get(batch_id)) is not None]

    def attach_plan(self, item_id: str, plan_id: str) -> None:
        with self._session_factory.begin() as session:
            session.execute(
                text("UPDATE story_items SET plan_id=:plan WHERE id=:id"),
                {"plan": plan_id, "id": item_id},
            )

    def update_item(
        self,
        item_id: str,
        *,
        status: str,
        output_path: Path | None = None,
        error_summary: str | None = None,
    ) -> None:
        with self._session_factory.begin() as session:
            session.execute(
                text(
                    """UPDATE story_items SET status=:status,output_path=:output,
                    error_summary=:error WHERE id=:id"""
                ),
                {
                    "status": status,
                    "output": None if output_path is None else str(output_path),
                    "error": error_summary,
                    "id": item_id,
                },
            )

    def set_status(self, batch_id: str, status: str) -> None:
        with self._session_factory.begin() as session:
            session.execute(
                text("UPDATE story_batches SET status=:status,updated_at=:now WHERE id=:id"),
                {"status": status, "now": self._clock().isoformat(), "id": batch_id},
            )

    def finish(self, batch_id: str) -> StoryBatch:
        batch = self.get(batch_id)
        statuses = {item.status for item in batch.items}
        if statuses == {"completed"}:
            final = "completed"
        elif "completed" in statuses:
            final = "partial"
        else:
            final = "failed"
        self.set_status(batch_id, final)
        return self.get(batch_id)

    def retry_failed(self, batch_id: str) -> StoryBatch:
        with self._session_factory.begin() as session:
            session.execute(
                text(
                    """UPDATE story_items SET status='queued',error_summary=NULL
                    WHERE batch_id=:id AND status='failed'"""
                ),
                {"id": batch_id},
            )
        self.set_status(batch_id, "queued")
        return self.get(batch_id)


def _date(value) -> datetime:
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return value.replace(tzinfo=value.tzinfo or UTC)
