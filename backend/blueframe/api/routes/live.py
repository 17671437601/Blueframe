from __future__ import annotations

from pathlib import PurePosixPath
from uuid import uuid4
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from blueframe.live.models import LivePlatform
from blueframe.security.project_paths import resolve_within_root


class StartRecordingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    platform: LivePlatform
    display_name: str = Field(min_length=1, max_length=300)
    playback_url: str = Field(min_length=8, max_length=8192)
    authorization_confirmed: bool


def build_live_router(auth, projects, recordings, credentials, engine, account_service) -> APIRouter:
    router = APIRouter(prefix="/projects", dependencies=[Depends(auth)])

    def project(project_id: str):
        found = projects.get(project_id)
        if found is None: raise HTTPException(404, detail={"code": "project_not_found", "message": "项目不存在"})
        return found

    def writable() -> None:
        if account_service.evaluate_access(datetime.now(UTC)).mode == "readonly":
            raise HTTPException(403, detail={"code": "account_readonly", "message": "当前账号仅允许查看和导出"})

    @router.get("/{project_id}/recordings")
    def list_recordings(project_id: str):
        project(project_id)
        return [_payload(item, recordings.list_segments(item.id)) for item in recordings.list(project_id)]

    @router.post("/{project_id}/recordings", status_code=status.HTTP_201_CREATED)
    def start_recording(project_id: str, request: StartRecordingRequest):
        current_project = project(project_id); writable()
        if not request.authorization_confirmed:
            raise HTTPException(400, detail={"code": "recording_authorization_required", "message": "请确认已获得录制和处理授权"})
        reference = credentials.put(f"live:{project_id}:{uuid4()}", request.playback_url)
        session = None
        try:
            session = recordings.create(
                project_id=project_id, platform=request.platform, display_name=request.display_name,
                source_reference=reference, authorization_confirmed=True,
            )
            output = resolve_within_root(current_project.root_path, (PurePosixPath(current_project.output_relative_path) / "live" / session.id).as_posix())
            engine.start(session.id, output)
            return _payload(recordings.get(session.id), ())
        except (ValueError, RuntimeError) as error:
            if session is not None: recordings.stop_intent(session.id, status="failed")
            credentials.delete(reference)
            raise HTTPException(400, detail={"code": "recording_start_failed", "message": str(error)[:300]}) from error

    @router.post("/{project_id}/recordings/{session_id}/stop")
    def stop_recording(project_id: str, session_id: str):
        project(project_id); writable(); session = recordings.get(session_id)
        if session is None or session.project_id != project_id:
            raise HTTPException(404, detail={"code": "recording_not_found", "message": "录制会话不存在"})
        engine.stop(session_id)
        try: credentials.delete(session.source_reference)
        except (KeyError, ValueError): pass
        return _payload(recordings.get(session_id), recordings.list_segments(session_id))

    @router.post("/{project_id}/recordings/{session_id}/reconnect")
    def reconnect(project_id: str, session_id: str):
        project(project_id); writable(); session = recordings.get(session_id)
        if session is None or session.project_id != project_id or not session.intent_active:
            raise HTTPException(404, detail={"code": "recording_not_found", "message": "活动录制会话不存在"})
        try: engine.reconnect(session_id)
        except RuntimeError as error: raise HTTPException(409, detail={"code": "reconnect_failed", "message": str(error)[:300]}) from error
        return _payload(recordings.get(session_id), recordings.list_segments(session_id))

    return router


def _payload(session, segments) -> dict:
    return {
        "id": session.id, "project_id": session.project_id, "platform": session.platform.value,
        "display_name": session.display_name, "intent_active": session.intent_active,
        "status": session.status, "reconnect_count": session.reconnect_count,
        "error_summary": session.error_summary, "created_at": session.created_at.isoformat(),
        "segments": [{
            "id": item.id, "sequence": item.sequence, "status": item.status,
            "filename": item.path.name, "duration_ms": item.duration_ms, "size_bytes": item.size_bytes,
        } for item in segments],
    }
