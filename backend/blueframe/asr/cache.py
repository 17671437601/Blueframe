from __future__ import annotations

import hashlib

from blueframe.projects.models import ProjectSource


def asr_cache_key(source: ProjectSource, model_version: str) -> str:
    material = "\0".join(
        (
            str(source.size_bytes),
            str(source.modified_ns),
            source.content_fingerprint,
            model_version,
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
