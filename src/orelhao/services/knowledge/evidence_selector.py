"""Seleção determinística de passagem por sobreposição lexical.

Não substitui NLI e não serve como autorização factual. A escolha não
utiliza score do NLI, para evitar maximização oportunista de entailment.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .evidence_span import EvidenceSpan, extract_evidence_spans
from .models import Chunk

_STOPWORDS = frozenset({
    "a", "as", "o", "os", "ao", "aos", "do", "dos", "da", "das", "de", "em",
    "no", "na", "nos", "nas", "e", "um", "uma", "uns", "umas", "para",
    "por", "com", "que", "qual", "quais", "como", "se", "tem", "sao",
    "ser", "foi", "era", "sobre", "este", "esta", "esse", "essa",
})


def _tokens(text: str) -> frozenset[str]:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    plain = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return frozenset(
        word for word in re.findall(r"[a-z0-9]+", plain)
        if word not in _STOPWORDS and len(word) >= 2
    )


@dataclass(frozen=True, slots=True)
class SpanSelection:
    span: EvidenceSpan
    matched_terms: tuple[str, ...]
    lexical_coverage: float

    def as_dict(self) -> dict[str, object]:
        return {
            "span": {
                "chunk_id": self.span.chunk_id,
                "source": self.span.source,
                "start": self.span.start,
                "end": self.span.end,
                "text": self.span.text,
                "source_url": self.span.source_url,
                "entity_id": self.span.entity_id,
                "attribute": self.span.attribute,
            },
            "matched_terms": list(self.matched_terms),
            "lexical_coverage": self.lexical_coverage,
            "support_verified": False,
        }


def select_evidence_span(
    claim: str, chunk: Chunk, *, max_span_chars: int = 480
) -> SpanSelection | None:
    """Escolhe uma passagem já existente sem validar que ela prova a claim.

    Em empate, prioriza a passagem mais curta e a primeira ocorrência.
    Se não houver termos relevantes compartilhados, retorna None.
    """
    terms = _tokens(claim)
    if not terms:
        return None
    best: tuple[int, float, int, int] | None = None
    selected: SpanSelection | None = None
    for span in extract_evidence_spans(chunk, max_span_chars=max_span_chars):
        common = terms & _tokens(span.text)
        if not common:
            continue
        coverage = len(common) / len(terms)
        rank = (len(common), coverage, -len(span.text), -span.start)
        if best is None or rank > best:
            best = rank
            selected = SpanSelection(span, tuple(sorted(common)), coverage)
    return selected
