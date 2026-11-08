from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from blueframe.jobs.repository import JobRepository
from blueframe.projects.models import Project, ProjectType, SourceRegistration
from blueframe.projects.repository import ProjectRepository
from blueframe.security.project_paths import ProjectPathRegistry, resolve_within_root


class CreateProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=300)
    project_type: ProjectType
    root_id: str
    output_relative_path: str = Field(min_length=1)
    config: dict
    idempotency_key: str = Field(min_length=1, max_length=200)


class AddSourcesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    relative_paths: list[str] = Field(min_length=1)


def build_projects_router(
    auth,
    repository: ProjectRepository,
    roots: ProjectPathRegistry,
    media_probe,
    jobs: JobRepository,
    account_service,
) -> APIRouter:
    router = APIRouter(prefix="/projects", dependencies=[Depends(auth)])

    def require_writable() -> None:
        from datetime import UTC, datetime

        access = account_service.evaluate_access(datetime.now(UTC))
        if access.mode == "readonly":
            raise HTTPException(
                403,
                detail={"code": "account_readonly", "message": "当前账号仅允许查看和导出"},
            )

    @router.get("")
    def list_projects():
        return [_project_payload(project) for project in repository.list()]

    @router.post("", status_code=status.HTTP_201_CREATED)
    def create_project(request: CreateProjectRequest):
        require_writable()
        try:
            root = roots.root(request.root_id)
            resolve_within_root(root, request.output_relative_path)
        except (KeyError, ValueError):
            raise HTTPException(
                400,
                detail={"code": "invalid_project_root", "message": "项目目录无效或未授权"},
            )
        project = repository.create(
            name=request.name,
            project_type=request.project_type,
            root_path=root,
            output_relative_path=request.output_relative_path,
            config=request.config,
            idempotency_key=request.idempotency_key,
        )
        return _project_payload(project)

    @router.get("/{project_id}")
    def get_project(project_id: str):
        project = repository.get(project_id)
        if project is None:
            raise HTTPException(
                404, detail={"code": "project_not_found", "message": "项目不存在"}
            )
        return _project_payload(project, repository.list_sources(project_id))

    @router.post("/{project_id}/sources", status_code=status.HTTP_201_CREATED)
    def add_sources(project_id: str, request: AddSourcesRequest):
        require_writable()
        project = repository.get(project_id)
        if project is None:
            raise HTTPException(
                404, detail={"code": "project_not_found", "message": "项目不存在"}
            )
        registrations: list[SourceRegistration] = []
        paths: list[Path] = []
        try:
            for relative_path in request.relative_paths:
                path = resolve_within_root(project.root_path, relative_path)
                if not path.is_file():
                    raise ValueError("source is not a file")
                stat = path.stat()
                registrations.append(
                    SourceRegistration(
                        relative_path=relative_path,
                        size_bytes=stat.st_size,
                        modified_ns=stat.st_mtime_ns,
                        content_fingerprint=_fingerprint(path),
                    )
                )
                paths.append(path)
        except (OSError, ValueError):
            raise HTTPException(
                400,
                detail={"code": "invalid_source_path", "message": "素材文件不存在或超出项目目录"},
            )
        sources = repository.add_sources(project_id, registrations)
        probed = []
        for source, path in zip(sources, paths, strict=True):
            info = media_probe(path)
            probed.append(
                repository.update_media_info(source.id, info.model_dump(mode="json"))
            )
        return [_source_payload(source) for source in probed]

    @router.post("/{project_id}/transcribe", status_code=status.HTTP_202_ACCEPTED)
    def transcribe_project(project_id: str):
        require_writable()
        project = repository.get(project_id)
        if project is None:
            raise HTTPException(
                404, detail={"code": "project_not_found", "message": "项目不存在"}
            )
        sources = repository.list_sources(project_id)
        identity = hashlib.sha256(
            "|".join(source.content_fingerprint for source in sources).encode("utf-8")
        ).hexdigest()[:16]
        job = jobs.create(
            "transcribe_project",
            {"project_id": project_id},
            f"transcribe:{project_id}:{identity}",
        )
        return job.model_dump(mode="json")

    return router


def _project_payload(project: Project, sources=()) -> dict:
    return {
        "id": project.id,
        "name": project.name,
        "project_type": project.project_type,
        "status": project.status,
        "output_relative_path": project.output_relative_path,
        "config": project.config.model_dump(mode="json"),
        "created_at": project.created_at,
        "updated_at": project.updated_at,
        "sources": [_source_payload(source) for source in sources],
    }


def _source_payload(source) -> dict:
    return source.model_dump(mode="json", exclude={"project_id"})


def _fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    size = path.stat().st_size
    with path.open("rb") as stream:
        digest.update(stream.read(1024 * 1024))
        if size > 1024 * 1024:
            stream.seek(max(0, size - 1024 * 1024))
            digest.update(stream.read(1024 * 1024))
    digest.update(str(size).encode("ascii"))
    return digest.hexdigest()
