from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from blueframe.commentary.models import CommentarySentence
from blueframe.commentary.service import CommentaryService


class GenerateCommentaryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    voice: str = Field(min_length=1, max_length=200)
    consent_to_send_transcript: bool
    idempotency_key: str = Field(min_length=1, max_length=200)


class EditCommentaryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    voice: str = Field(min_length=1, max_length=200)
    sentences: tuple[CommentarySentence, ...]


class RegenerateSentenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    consent_to_send_transcript: bool
    idempotency_key: str = Field(min_length=1, max_length=200)


def build_commentary_router(auth, projects, jobs, scripts, account_service, provider_config_service) -> APIRouter:
    router = APIRouter(prefix="/projects", dependencies=[Depends(auth)])

    def require_project(project_id: str):
        project = projects.get(project_id)
        if project is None:
            raise HTTPException(404, detail={"code": "project_not_found", "message": "项目不存在"})
        return project

    def require_remote_ai(consent: bool) -> None:
        if not consent:
            raise HTTPException(400, detail={"code": "transcript_consent_required", "message": "需要明确同意发送字幕文本"})
        if not provider_config_service.status().configured:
            raise HTTPException(409, detail={"code": "provider_not_configured", "message": "请先配置火山引擎"})
        if not account_service.evaluate_access(datetime.now(UTC), provider_available=True).remote_ai:
            raise HTTPException(403, detail={"code": "remote_ai_denied", "message": "当前账号不能使用远程 AI"})

    @router.get("/{project_id}/commentary")
    def list_scripts(project_id: str):
        require_project(project_id)
        return [item.model_dump(mode="json") for item in scripts.list_for_project(project_id)]

    @router.post("/{project_id}/commentary/generate", status_code=status.HTTP_202_ACCEPTED)
    def generate_script(project_id: str, request: GenerateCommentaryRequest):
        require_project(project_id); require_remote_ai(request.consent_to_send_transcript)
        return jobs.create("generate_commentary", {
            "project_id": project_id, "voice": request.voice, "transcript_consent": True,
        }, request.idempotency_key).model_dump(mode="json")

    @router.put("/{project_id}/commentary/{script_id}")
    def edit_script(project_id: str, script_id: str, request: EditCommentaryRequest):
        require_project(project_id)
        base = scripts.get(script_id)
        if base is None or base.project_id != project_id:
            raise HTTPException(404, detail={"code": "commentary_not_found", "message": "解说稿不存在"})
        edited = CommentaryService(None, scripts).edit(
            base=base, title=request.title, voice=request.voice, sentences=request.sentences,
        )
        return edited.model_dump(mode="json")

    @router.post("/{project_id}/commentary/{script_id}/sentences/{sentence_index}/regenerate", status_code=status.HTTP_202_ACCEPTED)
    def regenerate_sentence(project_id: str, script_id: str, sentence_index: int, request: RegenerateSentenceRequest):
        require_project(project_id); require_remote_ai(request.consent_to_send_transcript)
        base = scripts.get(script_id)
        if base is None or base.project_id != project_id:
            raise HTTPException(404, detail={"code": "commentary_not_found", "message": "解说稿不存在"})
        if sentence_index < 0 or sentence_index >= len(base.sentences):
            raise HTTPException(400, detail={"code": "sentence_out_of_range", "message": "句子序号无效"})
        return jobs.create("generate_commentary", {
            "project_id": project_id, "script_id": script_id, "sentence_index": sentence_index,
            "transcript_consent": True,
        }, request.idempotency_key).model_dump(mode="json")

    return router
