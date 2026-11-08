from __future__ import annotations

from pathlib import Path
from typing import Any

from blueframe.asr.models import EngineSegment


class FunAsrUnavailableError(RuntimeError):
    pass


class FunAsrEngine:
    def __init__(
        self,
        *,
        asr_model: Path,
        vad_model: Path,
        punctuation_model: Path,
        model_version: str = "seaco-paraformer-local-v1",
    ) -> None:
        self.asr_model = asr_model
        self.vad_model = vad_model
        self.punctuation_model = punctuation_model
        self.model_version = model_version
        self._model: Any | None = None

    def transcribe(self, audio_path: Path) -> list[EngineSegment]:
        model = self._load()
        result = model.generate(
            input=str(audio_path),
            language="auto",
            use_itn=True,
            batch_size_s=300,
        )
        if not result:
            return []
        item = result[0]
        sentence_info = item.get("sentence_info") or []
        segments = [
            EngineSegment(
                start_ms=max(0, int(sentence["start"])),
                end_ms=max(1, int(sentence["end"])),
                text=str(sentence["text"]).strip(),
            )
            for sentence in sentence_info
            if str(sentence.get("text", "")).strip()
        ]
        if segments:
            return segments
        text = str(item.get("text", "")).strip()
        timestamps = item.get("timestamp") or []
        if not text or not timestamps:
            return []
        return [
            EngineSegment(
                start_ms=int(timestamps[0][0]),
                end_ms=max(int(timestamps[-1][1]), int(timestamps[0][0]) + 1),
                text=text,
            )
        ]

    def _load(self):
        if self._model is not None:
            return self._model
        try:
            from funasr import AutoModel
        except ImportError as error:
            raise FunAsrUnavailableError(
                "本地语音模型运行时尚未安装，请安装蓝帧 ASR 模型包"
            ) from error
        self._model = AutoModel(
            model=str(self.asr_model),
            vad_model=str(self.vad_model),
            punc_model=str(self.punctuation_model),
            disable_update=True,
        )
        return self._model
