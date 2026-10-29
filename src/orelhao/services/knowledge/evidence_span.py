"""Localiza passagens literais com offsets dentro do chunk original.

A extração não implica entailment. O texto é uma fatia de Chunk.text, sem
paráfrases ou recomposição. Offsets são índices Python de caracteres Unicode.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Chunk

_BOUNDARY = re.compile(r"(?<=[.!?])(?=\s|$)|\n+")
_WORD = re.compile(r"\S+")


@dataclass(frozen=True, slots=True)
class EvidenceSpan:
    chunk_id: str
    source: str
    start: int
    end: int
    text: str
    source_url: str | None = None
    entity_id: str | None = None
    attribute: str | None = None

    @classmethod
    def from_chunk(cls, chunk: Chunk, start: int, end: int) -> EvidenceSpan:
        if not 0 <= start < end <= len(chunk.text):
            raise ValueError("offsets de evidência fora do chunk")
        return cls(
            chunk_id=chunk.id,
            source=chunk.source,
            start=start,
            end=end,
            text=chunk.text[start:end],
            source_url=_optional_metadata(chunk, "source_url"),
            entity_id=_optional_metadata(chunk, "entity_id"),
            attribute=_optional_metadata(chunk, "fact_key"),
        )

    def matches_chunk(self, chunk: Chunk) -> bool:
        return (
            self.chunk_id == chunk.id
            and self.source == chunk.source
            and 0 <= self.start < self.end <= len(chunk.text)
            and self.text == chunk.text[self.start:self.end]
        )


def _optional_metadata(chunk: Chunk, key: str) -> str | None:
    value = chunk.metadata.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _trim_bounds(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _split_long_segment(
    text: str, start: int, end: int, max_chars: int
) -> list[tuple[int, int]]:
    if end - start <= max_chars:
        return [(start, end)]
    words = list(_WORD.finditer(text, start, end))
    if not words:
        return []
    bounds: list[tuple[int, int]] = []
    left = words[0].start()
    right = words[0].end()
    for word in words[1:]:
        if word.end() - left > max_chars:
            bounds.append((left, right))
            left = word.start()
        right = word.end()
    bounds.append((left, right))
    return bounds


def extract_evidence_spans(
    chunk: Chunk, *, max_span_chars: int = 480, max_spans: int = 32
) -> tuple[EvidenceSpan, ...]:
    """Segmenta por frase/linha, com limites para CPU e sem alterar o texto.

    Uma palavra maior que max_span_chars é preservada inteira para não
    inventar fragmentos. Neste caso o caso deve ser auditado explicitamente.
    """
    if max_span_chars < 24 or max_spans <= 0:
        raise ValueError("limites de spans inválidos")
    spans: list[EvidenceSpan] = []
    cursor = 0
    for match in [*_BOUNDARY.finditer(chunk.text), None]:
        boundary = match.start() if match is not None else len(chunk.text)
        start, end = _trim_bounds(chunk.text, cursor, boundary)
        if start < end:
            for left, right in _split_long_segment(
                chunk.text, start, end, max_span_chars
            ):
                spans.append(EvidenceSpan.from_chunk(chunk, left, right))
                if len(spans) == max_spans:
                    return tuple(spans)
        cursor = match.end() if match is not None else len(chunk.text)
    return tuple(spans)
