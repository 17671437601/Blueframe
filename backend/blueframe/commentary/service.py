from __future__ import annotations

import asyncio
import re

from blueframe.asr.models import AsrDocument, AsrStatus
from blueframe.commentary.models import CommentaryScriptVersion, CommentarySentence, SourceCitation
from blueframe.commentary.repository import CommentaryRepository
from blueframe.commentary.schemas import commentary_schema
from blueframe.providers.ai import AiProvider, AiRequest


PROMPT_VERSION = "commentary-v1"


class CommentaryService:
    def __init__(self, provider: AiProvider, repository: CommentaryRepository, *, max_chunk_characters: int = 10_000) -> None:
        self.provider, self.repository = provider, repository
        self.max_chunk_characters = max_chunk_characters

    def generate(
        self, *, project_id: str, documents: tuple[AsrDocument, ...], voice: str,
    ) -> CommentaryScriptVersion:
        records = [
            {"source_id": document.source_id, "start_ms": line.start_ms, "end_ms": line.end_ms, "text": line.text}
            for document in documents if document.status is AsrStatus.COMPLETED for line in document.lines
        ]
        if not records:
            return self.repository.save(
                project_id=project_id, title="未命名解说", voice=voice,
                prompt_version=PROMPT_VERSION, provider="local", model="manual",
                sentences=(),
            )
        chunks = _chunk(records, self.max_chunk_characters)
        sentences: list[CommentarySentence] = []
        title = "影视解说"
        provider_name, model_name = "unknown", "unknown"
        for index, chunk in enumerate(chunks):
            result = asyncio.run(self.provider.execute(AiRequest(
                operation="movie_commentary_chunk",
                input={
                    "instruction": "仅根据给定字幕写简洁中文解说。每句话必须引用支持它的原字幕，不得补充无依据事实。",
                    "chunk_index": index, "transcript": chunk,
                },
                output_schema=commentary_schema(),
            )))
            provider_name, model_name = result.provider, result.model
            title = str(result.output["title"])
            for raw in result.output["sentences"]:
                sentence = CommentarySentence.model_validate(raw)
                _verify_citations(sentence.citations, records)
                sentences.append(sentence)
        return self.repository.save(
            project_id=project_id, title=title, voice=voice, prompt_version=PROMPT_VERSION,
            provider=provider_name, model=model_name, sentences=tuple(sentences),
        )

    def edit(
        self, *, base: CommentaryScriptVersion, title: str, voice: str,
        sentences: tuple[CommentarySentence, ...],
    ) -> CommentaryScriptVersion:
        return self.repository.save(
            project_id=base.project_id, title=title, voice=voice, prompt_version="manual-edit",
            provider="manual", model="local", sentences=sentences,
        )

    def regenerate_sentence(
        self, *, base: CommentaryScriptVersion, sentence_index: int, documents: tuple[AsrDocument, ...],
    ) -> CommentaryScriptVersion:
        if sentence_index < 0 or sentence_index >= len(base.sentences):
            raise IndexError("sentence index out of range")
        cited = base.sentences[sentence_index].citations
        allowed = [
            {"source_id": document.source_id, "start_ms": line.start_ms, "end_ms": line.end_ms, "text": line.text}
            for document in documents for line in document.lines
            if any(document.source_id == citation.source_id and line.end_ms > citation.start_ms and line.start_ms < citation.end_ms for citation in cited)
        ]
        result = asyncio.run(self.provider.execute(AiRequest(
            operation="movie_commentary_sentence_regeneration",
            input={"instruction": "重写一条解说，只能使用给定字幕事实。", "transcript": allowed},
            output_schema=commentary_schema(),
        )))
        replacements = result.output["sentences"]
        if len(replacements) != 1:
            raise ValueError("regeneration must return exactly one sentence")
        replacement = CommentarySentence.model_validate(replacements[0])
        _verify_citations(replacement.citations, allowed)
        sentences = list(base.sentences); sentences[sentence_index] = replacement
        return self.repository.save(
            project_id=base.project_id, title=base.title, voice=base.voice,
            prompt_version=PROMPT_VERSION, provider=result.provider, model=result.model,
            sentences=tuple(sentences),
        )


def _chunk(records: list[dict], limit: int) -> list[list[dict]]:
    chunks: list[list[dict]] = []
    current: list[dict] = []
    size = 0
    for record in records:
        record_size = len(record["text"]) + 40
        if current and size + record_size > limit:
            chunks.append(current); current, size = [], 0
        current.append(record); size += record_size
    if current: chunks.append(current)
    return chunks


def _normalized(value: str) -> str:
    return re.sub(r"\s+", "", value).casefold()


def _verify_citations(citations: tuple[SourceCitation, ...], records: list[dict]) -> None:
    for citation in citations:
        candidates = [record for record in records if record["source_id"] == citation.source_id
                      and record["start_ms"] <= citation.start_ms and record["end_ms"] >= citation.end_ms]
        quote = _normalized(citation.quote)
        if not candidates or not any(quote in _normalized(record["text"]) for record in candidates):
            raise ValueError("commentary citation cannot be verified against transcript")
