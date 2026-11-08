from __future__ import annotations

import asyncio
from dataclasses import dataclass

from pydantic import ValidationError

from blueframe.asr.models import AsrLine
from blueframe.drama.chunking import chunk_transcript
from blueframe.drama.models import StoryAnalysis, StoryAnalysisVersion
from blueframe.drama.prompts import PROMPT_VERSION, story_analysis_prompt
from blueframe.drama.repository import StoryAnalysisRepository
from blueframe.drama.schemas import story_analysis_schema
from blueframe.providers.ai import AiProvider, AiRequest, AiResult
from blueframe.workers.protocol import WorkerControl


@dataclass(frozen=True)
class AnalysisRunResult:
    version: StoryAnalysisVersion
    provider_calls: int


class AnalysisService:
    def __init__(
        self,
        provider: AiProvider,
        repository: StoryAnalysisRepository,
        *,
        max_chunk_characters: int = 12_000,
        overlap_lines: int = 2,
    ) -> None:
        self.provider = provider
        self.repository = repository
        self.max_chunk_characters = max_chunk_characters
        self.overlap_lines = overlap_lines

    def analyze(
        self,
        *,
        project_id: str,
        lines: tuple[AsrLine, ...],
        media_duration_ms: int,
        checkpoint: dict | None,
        control: WorkerControl,
    ) -> AnalysisRunResult | None:
        checkpoint = checkpoint or {}
        if checkpoint.get("analysis_version_id"):
            existing = self.repository.get(str(checkpoint["analysis_version_id"]))
            if existing is not None:
                return AnalysisRunResult(existing, 0)
        chunks = chunk_transcript(
            lines,
            max_characters=self.max_chunk_characters,
            overlap_lines=self.overlap_lines,
        )
        if not chunks:
            raise ValueError("项目没有可分析的字幕")
        outputs = [StoryAnalysis.model_validate(item) for item in checkpoint.get("chunk_outputs", [])]
        next_index = min(int(checkpoint.get("next_chunk_index", len(outputs))), len(chunks))
        outputs = outputs[:next_index]
        provider_calls = 0
        provider_name = str(checkpoint.get("provider") or "volcengine-ark")
        model_name = str(checkpoint.get("model") or "configured-model")
        for index in range(next_index, len(chunks)):
            if control.pause_requested or control.cancel_requested:
                return None
            request = AiRequest(
                operation="story_chunk_analysis",
                input={
                    **story_analysis_prompt(chunks[index].text, media_duration_ms),
                    "chunk_index": index,
                    "chunk_start_ms": chunks[index].start_ms,
                    "chunk_end_ms": chunks[index].end_ms,
                },
                output_schema=story_analysis_schema(),
            )
            result = asyncio.run(self.provider.execute(request))
            provider_calls += 1
            provider_name, model_name = result.provider, result.model
            try:
                mapped = StoryAnalysis.model_validate(result.output)
            except ValidationError as error:
                repair = AiRequest(
                    operation="story_chunk_repair",
                    input={
                        **request.input,
                        "repair": True,
                        "invalid_output": result.output,
                        "validation_error": str(error)[:1000],
                    },
                    output_schema=story_analysis_schema(),
                )
                result = asyncio.run(self.provider.execute(repair))
                provider_calls += 1
                mapped = StoryAnalysis.model_validate(result.output)
            outputs.append(mapped)
            control.checkpoint(
                {
                    "next_chunk_index": index + 1,
                    "chunk_outputs": [item.model_dump(mode="json") for item in outputs],
                    "provider": provider_name,
                    "model": model_name,
                }
            )
            control.progress((index + 1) / len(chunks) * 90, "analyze_story")
            control.heartbeat()
        merged = _merge(outputs, media_duration_ms)
        final = self.repository.save(
            project_id=project_id,
            prompt_version=PROMPT_VERSION,
            provider=provider_name,
            model=model_name,
            analysis=merged,
        )
        control.checkpoint(
            {
                "next_chunk_index": len(chunks),
                "chunk_outputs": [item.model_dump(mode="json") for item in outputs],
                "analysis_version_id": final.id,
                "provider": provider_name,
                "model": model_name,
            }
        )
        control.progress(100, "analyze_story")
        return AnalysisRunResult(final, provider_calls)


def _merge(outputs: list[StoryAnalysis], duration_ms: int) -> StoryAnalysis:
    summaries = list(dict.fromkeys(item.episode_summary for item in outputs))
    characters = {
        character.name: character
        for item in outputs
        for character in item.characters
    }
    conflicts = {
        (entry.start_ms, entry.end_ms, entry.summary): entry
        for item in outputs
        for entry in item.conflicts
    }
    explosions = {
        (entry.start_ms, entry.end_ms, entry.title): entry
        for item in outputs
        for entry in item.explosions
    }
    edits = {
        (entry.title, entry.segments): entry
        for item in outputs
        for entry in item.edit_candidates
    }
    return StoryAnalysis(
        episode_summary="\n".join(summaries),
        characters=tuple(characters.values()),
        conflicts=tuple(sorted(conflicts.values(), key=lambda item: item.start_ms)),
        explosions=tuple(sorted(explosions.values(), key=lambda item: (-item.score, item.start_ms))),
        edit_candidates=tuple(edits.values()),
        media_duration_ms=duration_ms,
    )
