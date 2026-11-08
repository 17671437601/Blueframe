from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Callable
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from blueframe.assets.models import Asset, AssetDraft


class AssetRepository:
    def __init__(self, session_factory: sessionmaker[Session], *, clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._session_factory, self._clock = session_factory, clock

    def save(self, draft: AssetDraft) -> Asset:
        existing = self.get_by_hash(draft.sha256)
        if existing is not None: return existing
        now, asset_id = self._clock(), str(uuid4())
        with self._session_factory.begin() as session:
            session.execute(text("""INSERT INTO assets
                (id,sha256,asset_type,path,origin,license_name,ownership,metadata_json,available,created_at,updated_at)
                VALUES (:id,:hash,:type,:path,:origin,:license,:ownership,:metadata,1,:created,:updated)"""), {
                "id": asset_id, "hash": draft.sha256, "type": draft.asset_type.value,
                "path": str(draft.path), "origin": draft.origin, "license": draft.license_name,
                "ownership": draft.ownership.value, "metadata": json.dumps(draft.metadata, ensure_ascii=False),
                "created": now.isoformat(), "updated": now.isoformat(),
            })
        return self.get(asset_id)

    def get(self, asset_id: str) -> Asset | None:
        with self._session_factory() as session:
            row = session.execute(text("SELECT * FROM assets WHERE id=:id"), {"id": asset_id}).mappings().first()
        return None if row is None else self._model(row)

    def get_by_hash(self, sha256: str) -> Asset | None:
        with self._session_factory() as session:
            row = session.execute(text("SELECT * FROM assets WHERE sha256=:hash"), {"hash": sha256}).mappings().first()
        return None if row is None else self._model(row)

    def list(self, *, asset_type: str | None = None) -> list[Asset]:
        query, values = "SELECT * FROM assets", {}
        if asset_type: query, values = query + " WHERE asset_type=:type", {"type": asset_type}
        with self._session_factory() as session:
            rows = session.execute(text(query + " ORDER BY created_at DESC"), values).mappings().all()
        return [self._model(row) for row in rows]

    def refresh_availability(self, asset_id: str) -> Asset:
        asset = self.get(asset_id)
        if asset is None: raise KeyError("asset not found")
        available, now = asset.path.is_file(), self._clock()
        with self._session_factory.begin() as session:
            session.execute(text("UPDATE assets SET available=:available,updated_at=:updated WHERE id=:id"), {
                "available": int(available), "updated": now.isoformat(), "id": asset_id,
            })
        return self.get(asset_id)

    @staticmethod
    def _model(row) -> Asset:
        def date(value): return datetime.fromisoformat(value) if isinstance(value, str) else value.replace(tzinfo=value.tzinfo or UTC)
        return Asset(
            id=row.id, sha256=row.sha256, asset_type=row.asset_type, path=row.path,
            origin=row.origin, license_name=row.license_name, ownership=row.ownership,
            metadata=json.loads(row.metadata_json), available=bool(row.available),
            created_at=date(row.created_at), updated_at=date(row.updated_at),
        )
