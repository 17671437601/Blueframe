from __future__ import annotations

from pathlib import Path
from typing import Callable, Protocol, Sequence

from blueframe.asr.cache import asr_cache_key
from blueframe.asr.models import AsrDocument, AsrStatus, EngineSegment
from blueframe.asr.repository import AsrRepository
from blueframe.media.probe import MediaInfo
from blueframe.projects.models import ProjectSource
from blueframe.workers.protocol import WorkerControl


class AsrEngine(Protocol):
    model_version: str
    def transcribe(self, audio_path: Path) -> Sequence[EngineSegment]: ...


AudioExtractor = Callable[[Path, Path], Path]


class AsrService:
    def __init__(
        self,
        repository: AsrRepository,
        engine: AsrEngine,
        *,
        audio_extractor: AudioExtractor,
    ) -> None:
        self.repository = repository
        self.engine = engine
        self.audio_extractor = audio_extractor

    def transcribe(
        self,
        source: ProjectSource,
        source_path: Path,
        media_info: MediaInfo,
        control: WorkerControl,
    ) -> AsrDocument:
        cache_key = asr_cache_key(source, self.engine.model_version)
        cached = self.repository.get_by_cache_key(cache_key)
        if cached is not None:
            return cached
        if not media_info.has_audio:
            document = self.repository.save(
                source_id=source.id,
                cache_key=cache_key,
                model_version=self.engine.model_version,
                language="none",
                duration_ms=media_info.duration_ms,
                status=AsrStatus.NO_AUDIO,
            )
            control.checkpoint({"asr_document_id": document.id, "stage": "no_audio"})
            control.progress(100, "asr_no_audio")
            return document

        audio_path = source_path.parent / ".blueframe-work" / "asr" / f"{source.id}.wav"
        control.progress(10, "extract_audio")
        self.audio_extractor(source_path, audio_path)
        control.checkpoint({"audio_path": str(audio_path), "stage": "audio_extracted"})
        control.progress(35, "recognize")
        segments = self.engine.transcribe(audio_path)
        document = self.repository.save(
            source_id=source.id,
            cache_key=cache_key,
            model_version=self.engine.model_version,
            language="zh",
            duration_ms=media_info.duration_ms,
            status=AsrStatus.COMPLETED,
            segments=segments,
        )
        control.checkpoint({"asr_document_id": document.id, "stage": "completed"})
        control.progress(100, "asr_completed")
        return document
