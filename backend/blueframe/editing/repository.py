from __future__ import annotations

from datetime import UTC, datetime
from typing import Callable
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from blueframe.editing.models import EditPlan, EditPlanDraft


class EditPlanRepository:
    def __init__(
        self, session_factory: sessionmaker[Session],
        *, clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock

    def save(self, project_id: str, draft: EditPlanDraft, *, idempotency_key: str) -> EditPlan:
        with self._session_factory.begin() as session:
            existing = session.execute(
                text("SELECT * FROM edit_plans WHERE project_id=:project AND idempotency_key=:key"),
                {"project": project_id, "key": idempotency_key},
            ).mappings().first()
            if existing is not None:
                return self._model(existing)
            version = int(session.execute(
                text("SELECT COALESCE(MAX(version),0)+1 FROM edit_plans WHERE project_id=:project"),
                {"project": project_id},
            ).scalar_one())
            item = EditPlan(
                **draft.model_dump(exclude_computed_fields=True), id=str(uuid4()),
                project_id=project_id, version=version, idempotency_key=idempotency_key,
                created_at=self._clock(),
            )
            session.execute(
                text("""INSERT INTO edit_plans
                (id, project_id, version, idempotency_key, plan_json, created_at)
                VALUES (:id,:project,:version,:key,:plan,:created)"""),
                {"id": item.id, "project": project_id, "version": version, "key": idempotency_key,
                 "plan": draft.model_dump_json(exclude_computed_fields=True), "created": item.created_at.isoformat()},
            )
            return item

    def list_for_project(self, project_id: str) -> list[EditPlan]:
        with self._session_factory() as session:
            rows = session.execute(
                text("SELECT * FROM edit_plans WHERE project_id=:project ORDER BY version DESC"),
                {"project": project_id},
            ).mappings().all()
            return [self._model(row) for row in rows]

    def get(self, plan_id: str) -> EditPlan | None:
        with self._session_factory() as session:
            row = session.execute(text("SELECT * FROM edit_plans WHERE id=:id"), {"id": plan_id}).mappings().first()
            return None if row is None else self._model(row)

    @staticmethod
    def _model(row) -> EditPlan:
        draft = EditPlanDraft.model_validate_json(row.plan_json)
        created = datetime.fromisoformat(row.created_at) if isinstance(row.created_at, str) else row.created_at.replace(tzinfo=row.created_at.tzinfo or UTC)
        return EditPlan(
            **draft.model_dump(exclude_computed_fields=True), id=row.id, project_id=row.project_id,
            version=row.version, idempotency_key=row.idempotency_key, created_at=created,
        )
