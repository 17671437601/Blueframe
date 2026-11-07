from __future__ import annotations

from pathlib import Path, PurePath
from uuid import uuid4


class ProjectPathRegistry:
    def __init__(self) -> None:
        self._roots: dict[str, Path] = {}

    def register(self, root: Path) -> str:
        resolved = root.resolve(strict=True)
        if not resolved.is_dir():
            raise ValueError("project root must be a directory")
        root_id = str(uuid4())
        self._roots[root_id] = resolved
        return root_id

    def resolve(self, root_id: str, relative_path: str) -> Path:
        root = self._roots.get(root_id)
        if root is None:
            raise KeyError(root_id)
        normalized = relative_path.replace("\\", "/")
        candidate_input = Path(normalized)
        if candidate_input.is_absolute() or ".." in PurePath(normalized).parts:
            raise ValueError("path escapes registered project root")
        candidate = (root / candidate_input).resolve(strict=False)
        if not candidate.is_relative_to(root):
            raise ValueError("path escapes registered project root")
        return candidate
