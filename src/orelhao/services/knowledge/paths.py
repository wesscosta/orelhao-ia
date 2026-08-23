from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from orelhao.runtime_paths import resolve_project_path


@dataclass(frozen=True, slots=True)
class KnowledgePaths:
    sources: Path
    index: Path


def default_knowledge_paths() -> KnowledgePaths:
    return KnowledgePaths(
        sources=resolve_project_path("knowledge/sources"),
        index=resolve_project_path("knowledge/index"),
    )
