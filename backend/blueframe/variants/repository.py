from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable
from uuid import uuid4

from pydantic import Field, field_validator
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from blueframe.domain.common import DomainModel, require_aware
from blueframe.variants.models import VariantRecipe


class VariantItem(DomainModel):
    id: str
    batch_id: str
    item_index: int = Field(ge=0)
    recipe: VariantRecipe
    status: str
    output_path: Path | None = None
    error_summary: str | None = None


class VariantBatch(DomainModel):
    id: str
    project_id: str
    source_id: str
    status: str
    items: tuple[VariantItem, ...]
    created_at: datetime
    updated_at: datetime
    _aware = field_validator("created_at", "updated_at")(require_aware)


class VariantBatchRepository:
    def __init__(self, session_factory: sessionmaker[Session], *, clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._session_factory, self._clock = session_factory, clock

    def create(self, *, project_id: str, source_id: str, recipes: tuple[VariantRecipe, ...]) -> VariantBatch:
        if not recipes: raise ValueError("variant batch requires at least one recipe")
        now, batch_id = self._clock(), str(uuid4())
        with self._session_factory.begin() as session:
            session.execute(text("""INSERT INTO variant_batches (id,project_id,source_id,status,created_at,updated_at)
                VALUES (:id,:project,:source,'queued',:created,:updated)"""), {
                "id": batch_id, "project": project_id, "source": source_id,
                "created": now.isoformat(), "updated": now.isoformat(),
            })
            for index, recipe in enumerate(recipes):
                session.execute(text("""INSERT INTO variant_items (id,batch_id,item_index,recipe_json,status)
                    VALUES (:id,:batch,:index,:recipe,'queued')"""), {
                    "id": str(uuid4()), "batch": batch_id, "index": index, "recipe": recipe.model_dump_json(),
                })
        return self.get(batch_id)

    def get(self, batch_id: str) -> VariantBatch | None:
        with self._session_factory() as session:
            row = session.execute(text("SELECT * FROM variant_batches WHERE id=:id"), {"id": batch_id}).mappings().first()
            if row is None: return None
            items = session.execute(text("SELECT * FROM variant_items WHERE batch_id=:id ORDER BY item_index"), {"id": batch_id}).mappings().all()
        return VariantBatch(
            id=row.id, project_id=row.project_id, source_id=row.source_id, status=row.status,
            items=tuple(VariantItem(
                id=item.id, batch_id=item.batch_id, item_index=item.item_index,
                recipe=VariantRecipe.model_validate_json(item.recipe_json), status=item.status,
                output_path=Path(item.output_path) if item.output_path else None, error_summary=item.error_summary,
            ) for item in items), created_at=_date(row.created_at), updated_at=_date(row.updated_at),
        )

    def list_for_project(self, project_id: str) -> list[VariantBatch]:
        with self._session_factory() as session:
            ids = session.execute(text("SELECT id FROM variant_batches WHERE project_id=:project ORDER BY created_at DESC"), {"project": project_id}).scalars().all()
        return [self.get(batch_id) for batch_id in ids]

    def update_item(self, item_id: str, *, status: str, output_path: Path | None = None, error_summary: str | None = None) -> None:
        with self._session_factory.begin() as session:
            session.execute(text("""UPDATE variant_items SET status=:status,output_path=:output,error_summary=:error WHERE id=:id"""), {
                "status": status, "output": None if output_path is None else str(output_path), "error": error_summary, "id": item_id,
            })

    def finish(self, batch_id: str) -> VariantBatch:
        batch = self.get(batch_id)
        statuses = {item.status for item in batch.items}
        final = "completed" if statuses == {"completed"} else "partial" if "completed" in statuses else "failed"
        self.set_status(batch_id, final)
        return self.get(batch_id)

    def set_status(self, batch_id: str, status: str) -> None:
        with self._session_factory.begin() as session:
            session.execute(text("UPDATE variant_batches SET status=:status,updated_at=:updated WHERE id=:id"), {
                "status": status, "updated": self._clock().isoformat(), "id": batch_id,
            })

    def retry_failed(self, batch_id: str) -> VariantBatch:
        with self._session_factory.begin() as session:
            session.execute(text("UPDATE variant_items SET status='queued',error_summary=NULL WHERE batch_id=:id AND status='failed'"), {"id": batch_id})
        self.set_status(batch_id, "queued")
        return self.get(batch_id)


def _date(value):
    return datetime.fromisoformat(value) if isinstance(value, str) else value.replace(tzinfo=value.tzinfo or UTC)
