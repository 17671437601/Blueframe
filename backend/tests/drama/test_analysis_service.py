from __future__ import annotations

from pathlib import Path

from blueframe.asr.models import AsrLine
from blueframe.domain.common import ProviderUsage
from blueframe.drama.analysis_service import AnalysisService
from blueframe.drama.repository import StoryAnalysisRepository
from blueframe.projects.models import ProjectType
from blueframe.projects.repository import ProjectRepository
from blueframe.providers.ai import AiResult


class SequenceProvider:
    def __init__(self, outputs: list[dict]) -> None:
        self.outputs = outputs
        self.calls = []

    async def execute(self, request):
        self.calls.append(request)
        output = self.outputs.pop(0)
        return AiResult(
            provider="fixture", model="model-a",
            usage=ProviderUsage(input_units=10, output_units=5), output=output,
        )


class Control:
    pause_requested = False
    cancel_requested = False

    def __init__(self) -> None:
        self.checkpoints = []
        self.progress_values = []

    def checkpoint(self, value): self.checkpoints.append(value)
    def progress(self, value, stage=None): self.progress_values.append((value, stage))
    def heartbeat(self): pass


def output(duration=10_000, *, summary="片段") -> dict:
    return {
        "episode_summary": summary,
        "characters": [{"name": "林夏", "role": "主角", "description": "记者"}],
        "conflicts": [], "explosions": [], "edit_candidates": [],
        "media_duration_ms": duration,
    }


def make_project(session_factory) -> str:
    return ProjectRepository(session_factory).create(
        name="Analysis", project_type=ProjectType.DRAMA, root_path=Path("C:/analysis"),
        output_relative_path="out", config={}, idempotency_key="analysis-service-project",
    ).id


def lines() -> tuple[AsrLine, ...]:
    return tuple(
        AsrLine(index=i, start_ms=i * 1000, end_ms=(i + 1) * 1000, text=f"第{i}句重要剧情")
        for i in range(5)
    )


def test_analysis_maps_chunks_resumes_and_saves_one_version(migrated_session_factory) -> None:
    project_id = make_project(migrated_session_factory)
    provider = SequenceProvider([output(summary="中段"), output(summary="末段")])
    service = AnalysisService(
        provider, StoryAnalysisRepository(migrated_session_factory),
        max_chunk_characters=70, overlap_lines=1,
    )
    checkpoint = {"chunk_outputs": [output(summary="开场")], "next_chunk_index": 1}
    control = Control()

    result = service.analyze(
        project_id=project_id, lines=lines(), media_duration_ms=10_000,
        checkpoint=checkpoint, control=control,
    )

    assert result.provider_calls == 2
    assert len(provider.calls) == 2
    assert result.version.version == 1
    assert len(StoryAnalysisRepository(migrated_session_factory).list_for_project(project_id)) == 1
    assert control.checkpoints[-1]["analysis_version_id"] == result.version.id


def test_invalid_domain_output_is_repaired_once(migrated_session_factory) -> None:
    project_id = make_project(migrated_session_factory)
    invalid = {**output(), "explosions": [{"start_ms": 0, "end_ms": 1000, "title": "x", "reason": "x", "score": 101}]}
    provider = SequenceProvider([invalid, output()])
    service = AnalysisService(provider, StoryAnalysisRepository(migrated_session_factory), max_chunk_characters=1000)

    result = service.analyze(
        project_id=project_id, lines=lines(), media_duration_ms=10_000,
        checkpoint=None, control=Control(),
    )

    assert result.provider_calls == 2
    assert provider.calls[-1].input["repair"] is True
