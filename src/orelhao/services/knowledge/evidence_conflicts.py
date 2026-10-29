"""Conflitos verificáveis entre fatos estruturados; não infere fatos de prosa."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from .models import SearchResult
from .source_policy import parse_date


@dataclass(frozen=True, slots=True)
class EvidenceConflict:
    key: str
    chunk_ids: tuple[str, ...]


def conflicting_facts(evidence: list[SearchResult], *, as_of: date) -> tuple[EvidenceConflict, ...]:
    facts: dict[tuple[str, str, str, str], dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    for result in evidence:
        m = result.chunk.metadata
        keys = ("entity_id", "fact_key", "fact_value", "authority")
        if not all(isinstance(m.get(key), str) and str(m[key]).strip() for key in keys):
            continue
        if m["authority"] != "primary":
            continue
        start = parse_date(m.get("valid_from"))
        end = parse_date(m.get("valid_until"))
        if start and as_of < start:
            continue
        if end and as_of > end:
            continue
        key = (
            str(m["entity_id"]).casefold(),
            str(m.get("unit_id", "")).casefold(),
            str(m["fact_key"]).casefold(),
            str(m.get("effective_date", "")).casefold(),
        )
        facts[key][str(m["fact_value"]).strip().casefold()].add(result.chunk.id)
    conflicts: list[EvidenceConflict] = []
    for key, values in facts.items():
        if len(values) >= 2:
            conflicts.append(EvidenceConflict("/".join(key), tuple(sorted(
                {chunk for ids in values.values() for chunk in ids}
            ))))
    return tuple(sorted(conflicts, key=lambda item: item.key))
