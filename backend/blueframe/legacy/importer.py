from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import Field
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from blueframe.domain.common import DomainModel


_EXCLUDED = {"account", "admin", "key", "notice"}
_SCHEMAS = {
    "drama_project": ({"id", "name", "source_path", "duration", "width", "height", "status", "settings"}, "drama"),
    "movie_project": ({"id", "name", "source_path", "source_duration", "width", "height", "status", "settings"}, "movie"),
}


class LegacyProjectPreview(DomainModel):
    legacy_table: str
    legacy_id: str
    name: str
    project_type: str
    source_available: bool
    duration_ms: int = Field(ge=0)


class LegacyPreviewReport(DomainModel):
    source_hash: str
    migration_version: str = "legacy-v1"
    projects: tuple[LegacyProjectPreview, ...]
    excluded_tables: tuple[str, ...]
    warnings: tuple[str, ...]


class LegacyImportResult(DomainModel):
    source_hash: str
    imported: int
    skipped: int
    project_ids: tuple[str, ...]


class LegacyImporter:
    def __init__(self, session_factory: sessionmaker[Session], *, media_probe=None, clock=lambda: datetime.now(UTC)) -> None:
        self.session_factory, self.media_probe, self.clock = session_factory, media_probe, clock

    def preview(self, database: Path) -> LegacyPreviewReport:
        database = database.resolve()
        source_hash = _sha256(database)
        warnings: list[str] = []
        projects: list[LegacyProjectPreview] = []
        with _readonly(database) as legacy:
            tables = {row[0] for row in legacy.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            excluded = tuple(sorted(tables & _EXCLUDED))
            for table, (required, project_type) in _SCHEMAS.items():
                if table not in tables: continue
                columns = {row[1] for row in legacy.execute(f"PRAGMA table_info({table})")}
                if not required <= columns:
                    warnings.append(f"{table} schema is partial or unknown; skipped")
                    continue
                duration_column = "duration" if table == "drama_project" else "source_duration"
                rows = legacy.execute(f"SELECT id,name,source_path,{duration_column} FROM {table}").fetchall()
                for legacy_id, name, source_path, duration in rows:
                    projects.append(LegacyProjectPreview(
                        legacy_table=table, legacy_id=str(legacy_id), name=str(name or "未命名旧项目"),
                        project_type=project_type, source_available=Path(str(source_path or "")).is_file(),
                        duration_ms=max(0, round(float(duration or 0) * 1000)),
                    ))
            unknown = sorted(table for table in tables if table.startswith(("drama_", "movie_")) and table not in _SCHEMAS)
            if unknown: warnings.append("Unmapped legacy workflow tables were left untouched: " + ", ".join(unknown))
        return LegacyPreviewReport(
            source_hash=source_hash, projects=tuple(projects), excluded_tables=excluded,
            warnings=tuple(warnings),
        )

    def import_confirmed(self, database: Path, *, expected_source_hash: str, confirmed: bool) -> LegacyImportResult:
        if not confirmed: raise ValueError("explicit legacy import confirmation is required")
        report = self.preview(database)
        if report.source_hash != expected_source_hash: raise ValueError("legacy database changed after preview")
        imported = skipped = 0; project_ids: list[str] = []
        with _readonly(database.resolve()) as legacy, self.session_factory.begin() as session:
            for preview in report.projects:
                existing = session.execute(text("""SELECT new_project_id FROM legacy_imports
                    WHERE source_hash=:hash AND legacy_table=:table AND legacy_id=:legacy"""), {
                    "hash": report.source_hash, "table": preview.legacy_table, "legacy": preview.legacy_id,
                }).scalar_one_or_none()
                if existing: skipped += 1; project_ids.append(existing); continue
                row = legacy.execute(
                    f"SELECT name,source_path,settings FROM {preview.legacy_table} WHERE id=?", (preview.legacy_id,),
                ).fetchone()
                if row is None: continue
                name, source_path, settings_json = row
                source = Path(str(source_path or "")).resolve()
                root = source.parent if source.is_file() else database.resolve().parent
                settings = _safe_settings(settings_json)
                project_id, now = str(uuid4()), self.clock()
                session.execute(text("""INSERT INTO projects
                    (id,name,project_type,status,root_path,output_relative_path,config_version,config_json,idempotency_key,created_at,updated_at)
                    VALUES (:id,:name,:type,:status,:root,:output,1,:config,:key,:created,:updated)"""), {
                    "id": project_id, "name": str(name or "未命名旧项目"), "type": preview.project_type,
                    "status": "ready" if source.is_file() and self.media_probe else "draft", "root": str(root),
                    "output": "BlueFrame-导入交付", "config": json.dumps({"legacy_migration": "legacy-v1", **settings}, ensure_ascii=False),
                    "key": f"legacy:{report.source_hash}:{preview.legacy_table}:{preview.legacy_id}",
                    "created": now.isoformat(), "updated": now.isoformat(),
                })
                if source.is_file() and self.media_probe:
                    info = self.media_probe(source); stat = source.stat(); fingerprint = _sha256(source)
                    session.execute(text("""INSERT INTO project_sources
                        (id,project_id,relative_path,order_index,size_bytes,modified_ns,content_fingerprint,media_info_json,created_at,updated_at)
                        VALUES (:id,:project,:path,0,:size,:modified,:fingerprint,:info,:created,:updated)"""), {
                        "id": str(uuid4()), "project": project_id, "path": source.name, "size": stat.st_size,
                        "modified": stat.st_mtime_ns, "fingerprint": fingerprint,
                        "info": json.dumps(info.model_dump(mode="json"), ensure_ascii=False),
                        "created": now.isoformat(), "updated": now.isoformat(),
                    })
                session.execute(text("""INSERT INTO legacy_imports
                    (id,source_hash,legacy_table,legacy_id,new_project_id,migration_version,imported_at)
                    VALUES (:id,:hash,:table,:legacy,:project,'legacy-v1',:imported)"""), {
                    "id": str(uuid4()), "hash": report.source_hash, "table": preview.legacy_table,
                    "legacy": preview.legacy_id, "project": project_id, "imported": now.isoformat(),
                })
                imported += 1; project_ids.append(project_id)
        return LegacyImportResult(source_hash=report.source_hash, imported=imported, skipped=skipped, project_ids=tuple(project_ids))


def _readonly(path: Path):
    if not path.is_file(): raise ValueError("legacy database does not exist")
    return sqlite3.connect(f"{path.as_uri()}?mode=ro&immutable=1", uri=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""): digest.update(block)
    return digest.hexdigest()


def _safe_settings(value) -> dict:
    try: raw = json.loads(value or "{}")
    except (TypeError, json.JSONDecodeError): return {}
    if not isinstance(raw, dict): return {}
    allowed = {"target_duration", "output_width", "output_height", "output_fps"}
    return {key: raw[key] for key in allowed if key in raw and isinstance(raw[key], (int, float, str, bool))}
