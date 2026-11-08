from __future__ import annotations

import asyncio
import subprocess
import os
from pathlib import Path
from typing import Protocol

from pydantic import Field, model_validator

from blueframe.commentary.models import CommentaryScriptVersion, SourceCitation
from blueframe.domain.common import DomainModel
from blueframe.providers.tts import TtsProvider, TtsRequest


class VoiceEntry(DomainModel):
    sentence_index: int = Field(ge=0)
    text: str = Field(min_length=1)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    citations: tuple[SourceCitation, ...] = ()

    @model_validator(mode="after")
    def valid_range(self) -> "VoiceEntry":
        if self.end_ms <= self.start_ms:
            raise ValueError("voice entry end must be after start")
        return self


class VoiceTimeline(DomainModel):
    narration_path: Path
    duration_ms: int = Field(ge=0)
    entries: tuple[VoiceEntry, ...]


class AudioAssembler(Protocol):
    def assemble(self, inputs: list[Path], output: Path) -> None: ...


class FfmpegAudioAssembler:
    def __init__(self, ffmpeg: Path) -> None:
        self.ffmpeg = ffmpeg

    def assemble(self, inputs: list[Path], output: Path) -> None:
        if not inputs:
            raise ValueError("narration has no audio clips")
        output.parent.mkdir(parents=True, exist_ok=True)
        command = [str(self.ffmpeg), "-hide_banner", "-nostdin", "-y"]
        for path in inputs: command.extend(["-i", str(path)])
        labels = []
        filters = []
        for index in range(len(inputs)):
            filters.append(f"[{index}:a:0]aresample=48000,asetpts=PTS-STARTPTS[a{index}]")
            labels.append(f"[a{index}]")
        filters.append(f"{''.join(labels)}concat=n={len(inputs)}:v=0:a=1[aout]")
        command.extend(["-filter_complex", ";".join(filters), "-map", "[aout]", "-c:a", "libmp3lame", str(output)])
        completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if completed.returncode != 0:
            raise RuntimeError(f"FFmpeg narration assembly failed ({completed.returncode})")


class VoiceTimelineService:
    def __init__(self, tts: TtsProvider, assembler: AudioAssembler, *, max_characters: int = 300, speech_rate: int = 0) -> None:
        self.tts, self.assembler = tts, assembler
        self.max_characters, self.speech_rate = max_characters, speech_rate

    def synthesize(self, script: CommentaryScriptVersion, output_root: Path) -> VoiceTimeline:
        output_root.mkdir(parents=True, exist_ok=True)
        audio_paths: list[Path] = []
        entries: list[VoiceEntry] = []
        cursor = 0
        for sentence_index, sentence in enumerate(script.sentences):
            sentence_start = cursor
            for part_index, part in enumerate(split_for_tts(sentence.text, self.max_characters)):
                result = asyncio.run(self.tts.synthesize(TtsRequest(
                    text=part, voice=script.voice, output_root=output_root,
                    filename=f"{script.id}-{sentence_index:04d}-{part_index:03d}.mp3",
                    speech_rate=self.speech_rate,
                )))
                if result.duration_ms <= 0:
                    raise ValueError("TTS returned an empty audio clip")
                audio_paths.append(result.audio_path)
                cursor += result.duration_ms
            entries.append(VoiceEntry(
                sentence_index=sentence_index, text=sentence.text,
                start_ms=sentence_start, end_ms=cursor, citations=sentence.citations,
            ))
        narration_path = output_root / f"{script.id}-v{script.version}-narration.mp3"
        temporary_narration = narration_path.with_suffix(".partial.mp3")
        self.assembler.assemble(audio_paths, temporary_narration)
        os.replace(temporary_narration, narration_path)
        return VoiceTimeline(narration_path=narration_path, duration_ms=cursor, entries=tuple(entries))


def write_timeline_manifest(timeline: VoiceTimeline, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(timeline.model_dump_json(indent=2), encoding="utf-8")
    os.replace(temporary, path)
    return path


def load_timeline_manifest(path: Path) -> VoiceTimeline:
    return VoiceTimeline.model_validate_json(path.read_text("utf-8"))


def split_for_tts(text: str, max_characters: int = 300) -> tuple[str, ...]:
    if max_characters < 1:
        raise ValueError("max_characters must be positive")
    parts: list[str] = []
    remaining = text
    punctuation = set("。！？!?；;，,、：:\n")
    while len(remaining) > max_characters:
        window = remaining[:max_characters]
        boundary = max((index + 1 for index, char in enumerate(window) if char in punctuation), default=max_characters)
        parts.append(remaining[:boundary])
        remaining = remaining[boundary:]
    if remaining: parts.append(remaining)
    return tuple(parts)
