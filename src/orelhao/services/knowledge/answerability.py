"""Gate pré-geração: decide impedimentos verificáveis, sem prometer resposta certa.

O resultado 'answerable' significa *sem impedimento detectado*. Na ausência
de fatos estruturados, a validação factual permanece responsabilidade do NLI.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from .evidence_conflicts import conflicting_facts
from .evidence_decision import AbstentionReason, EvidenceDecision
from .models import SearchResult
from .query_constraints import QueryConstraints, parse_query_constraints
from .source_policy import current_state_is_verified, source_matches


@dataclass(frozen=True, slots=True)
class EvidenceAssessment:
    decision: EvidenceDecision
    constraints: QueryConstraints
    admissible_chunk_ids: tuple[str, ...]
    conflicting_chunk_ids: tuple[str, ...] = ()
    verified_specific_answer: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "answerable": self.decision.answerable,
            "reason": self.decision.reason.value if self.decision.reason else None,
            "admissible_chunk_ids": list(self.admissible_chunk_ids),
            "conflicting_chunk_ids": list(self.conflicting_chunk_ids),
            "verified_specific_answer": self.verified_specific_answer,
            "constraints": {
                "entity_id": self.constraints.entity_id,
                "unit_id": self.constraints.unit_id,
                "attribute": self.constraints.attribute,
                "requires_current_state": self.constraints.requires_current_state,
                "reference_date": (
                    self.constraints.reference_date.isoformat()
                    if self.constraints.reference_date else None
                ),
            },
        }


class EvidenceAdjudicator:
    def __init__(self, *, known_entities: Iterable[str] = ()) -> None:
        # Catálogo indexado completo, não apenas os chunks do top-k.
        self._known_entities = tuple(sorted(set(known_entities)))

    def assess(
        self, question: str, evidence: list[SearchResult], *, as_of: date,
    ) -> EvidenceAssessment:
        constraints = parse_query_constraints(
            question,
            as_of=as_of,
            known_entities=[
                *self._known_entities,
                *(
                    str(item.chunk.metadata["entity_id"])
                    for item in evidence if item.chunk.metadata.get("entity_id")
                ),
            ],
        )
        if not evidence:
            return EvidenceAssessment(
                EvidenceDecision.abstain(AbstentionReason.NO_RELEVANT_EVIDENCE), constraints, ()
            )
        matched = [item for item in evidence if source_matches(item.chunk.metadata, constraints)]
        if constraints.unit_id and constraints.attribute in {
            "contact", "address", "schedule", "price", "availability",
        }:
            matched = [
                item for item in matched if item.chunk.metadata.get("unit_id") is not None
            ]
        if constraints.entity_id and constraints.attribute in {
            "price", "duration", "schedule", "availability",
        }:
            matched = [
                item for item in matched if item.chunk.metadata.get("entity_id") is not None
            ]
        if not matched:
            return EvidenceAssessment(
                EvidenceDecision.abstain(AbstentionReason.ENTITY_MISMATCH), constraints, ()
            )
        if constraints.requires_current_state:
            matched = [
                item for item in matched if current_state_is_verified(
                    item.chunk.metadata, constraints, as_of=as_of
                )
            ]
            if not matched:
                return EvidenceAssessment(
                    EvidenceDecision.abstain(AbstentionReason.TEMPORAL_EVIDENCE_UNAVAILABLE),
                    constraints, (),
                )
        declared_facts = [item for item in matched if item.chunk.metadata.get("fact_key")]
        if declared_facts and len(declared_facts) == len(matched) and constraints.attribute:
            matched = [
                item for item in matched
                if item.chunk.metadata.get("fact_key") == constraints.attribute
            ]
            if not matched:
                return EvidenceAssessment(
                    EvidenceDecision.abstain(AbstentionReason.SPECIFIC_INFORMATION_MISSING),
                    constraints, (),
                )
        conflicts = conflicting_facts(matched, as_of=as_of)
        if conflicts:
            return EvidenceAssessment(
                EvidenceDecision.abstain(AbstentionReason.CONFLICTING_EVIDENCE),
                constraints,
                tuple(item.chunk.id for item in matched),
                tuple(sorted({cid for item in conflicts for cid in item.chunk_ids})),
            )
        # Dados sem campo de fato estruturado exigem confirmação pós-geração.
        specific = any(
            item.chunk.metadata.get("fact_key") == constraints.attribute
            and item.chunk.metadata.get("fact_value") is not None
            for item in matched
        )
        return EvidenceAssessment(
            EvidenceDecision.answer(), constraints,
            tuple(item.chunk.id for item in matched),
            verified_specific_answer=specific,
        )
