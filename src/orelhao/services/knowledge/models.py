from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


Metadata = Mapping[str, str]


@dataclass(frozen=True, slots=True)
class Document:
    """Documento lógico fornecido pela implantação."""

    id: str
    text: str
    source: str
    title: str | None = None
    metadata: Metadata = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("Document.id não pode ser vazio")
        if not self.text.strip():
            raise ValueError("Document.text não pode ser vazio")
        if not self.source.strip():
            raise ValueError("Document.source não pode ser vazio")


@dataclass(frozen=True, slots=True)
class Chunk:
    """Unidade recuperável derivada de um documento."""

    id: str
    document_id: str
    text: str
    source: str
    position: int
    metadata: Metadata = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Chunk recuperado acompanhado de score normalizado."""

    chunk: Chunk
    score: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("SearchResult.score deve estar entre 0 e 1")


@dataclass(frozen=True, slots=True)
class KnowledgeContext:
    """Contexto final pronto para ser entregue ao LLM."""

    query: str
    text: str
    results: tuple[SearchResult, ...]

    @property
    def has_evidence(self) -> bool:
        return bool(self.results and self.text.strip())
