from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator, model_validator

from blueframe.domain.common import DomainModel, require_aware


class SourceCitation(DomainModel):
    source_id: str = Field(min_length=1)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    quote: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def valid_range(self) -> "SourceCitation":
        if self.end_ms <= self.start_ms:
            raise ValueError("citation end must be after start")
        return self


class CommentarySentence(DomainModel):
    text: str = Field(min_length=1, max_length=2000)
    citations: tuple[SourceCitation, ...] = ()
    manual: bool = False

    @model_validator(mode="after")
    def generated_claims_are_cited(self) -> "CommentarySentence":
        if not self.manual and not self.citations:
            raise ValueError("generated commentary sentence requires a citation")
        return self


class CommentaryScriptVersion(DomainModel):
    id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=200)
    voice: str = Field(min_length=1, max_length=200)
    prompt_version: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    sentences: tuple[CommentarySentence, ...] = ()
    created_at: datetime

    _aware = field_validator("created_at")(require_aware)
