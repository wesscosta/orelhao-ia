"""Fact Validator V3 em modo diagnóstico; não controla ALLOW/ABSTAIN.

Valida correspondência tipada de valores explícitos, escopo, origem e vigência.
Match de valores não equivale a prova semântica da afirmação completa.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from .fact_extraction import ExtractedFact, extract_explicit_facts, normalize
from .models import SearchResult
from .query_constraints import explicitly_named_entities
from .source_policy import parse_date


class FactStatus(StrEnum):
    VALUE_MATCH = "value_match"
    VALUE_MISMATCH = "value_mismatch"
    AMBIGUOUS = "ambiguous"
    NO_ADMISSIBLE_SOURCE = "no_admissible_source"
    INSUFFICIENT_CONTEXT = "insufficient_context"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, slots=True)
class FactCheck:
    fact: ExtractedFact
    status: FactStatus
    source: str | None = None
    chunk_id: str | None = None
    supporting_literal: str | None = None
    explanation: str = ""
    source_start: int | None = None
    source_end: int | None = None
    source_url: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "fact": self.fact.as_dict(), "status": self.status.value,
            "source": self.source, "chunk_id": self.chunk_id,
            "supporting_literal": self.supporting_literal,
            "source_start": self.source_start,
            "source_end": self.source_end,
            "source_url": self.source_url,
            "explanation": self.explanation,
        }


@dataclass(frozen=True, slots=True)
class FactValidation:
    checks: tuple[FactCheck, ...]
    status: FactStatus

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "checks": [check.as_dict() for check in self.checks],
            "full_claim_verified": False,
            "enforced": False,
        }


def _authorized(
    result: SearchResult, *, entity_id: str | None,
    unit_id: str | None, as_of: date, current: bool,
) -> bool:
    m = result.chunk.metadata
    if m.get("authority") != "primary":
        return False
    source_url = m.get("source_url")
    if not isinstance(source_url, str) or not source_url.startswith("https://"):
        return False
    if entity_id is not None and normalize(str(m.get("entity_id", ""))) != normalize(entity_id):
        return False
    if unit_id is not None and normalize(str(m.get("unit_id", ""))) != normalize(unit_id):
        return False
    valid_from = parse_date(m.get("valid_from"))
    valid_until = parse_date(m.get("valid_until"))
    if valid_from and as_of < valid_from:
        return False
    if valid_until and as_of > valid_until:
        return False
    if current:
        confirmation: object = m.get("current_state_confirmed")
        if confirmation is not True:
            return False
        if parse_date(m.get("verified_at")) != as_of or valid_until is None:
            return False
    return True


def _aligned(fact: ExtractedFact, source: ExtractedFact) -> bool:
    if fact.kind != source.kind:
        return False
    if fact.reference_id and fact.reference_id != source.reference_id:
        return False
    if fact.qualifier != source.qualifier:
        return False
    # Um prazo sem "úteis/corridos" não comprova nem refuta a unidade específica.
    return not (
        "unspecified_days" in (fact.unit, source.unit)
        and fact.unit != source.unit
    )


def _check_one(
    fact: ExtractedFact, evidence: list[SearchResult],
    *, as_of: date, entity_id: str | None, unit_id: str | None,
    current: bool,
) -> FactCheck:
    candidates: list[tuple[ExtractedFact, SearchResult]] = []
    for result in evidence:
        if not _authorized(
            result, entity_id=entity_id, unit_id=unit_id, as_of=as_of, current=current,
        ):
            continue
        for atom in extract_explicit_facts(result.chunk.text):
            if _aligned(fact, atom):
                candidates.append((atom, result))
    if not candidates:
        return FactCheck(
            fact, FactStatus.NO_ADMISSIBLE_SOURCE,
            explanation="Fonte primária válida, escopo ou qualificador não comprovado",
        )
    # A comparação só vale dentro de um conjunto de candidatos do mesmo escopo.
    values = {(a.value, a.unit) for a, _ in candidates}
    if len(values) > 1:
        return FactCheck(
            fact, FactStatus.AMBIGUOUS,
            explanation="Valores distintos no mesmo escopo: turma, unidade ou data não resolvida",
        )
    atom, result = candidates[0]
    if (fact.value, fact.unit) == (atom.value, atom.unit):
        status = FactStatus.VALUE_MATCH
        explanation = "Valor tipado coincide; não comprova toda a frase"
    else:
        status = FactStatus.VALUE_MISMATCH
        explanation = "Valor ou unidade divergente em fonte única do mesmo escopo"
    return FactCheck(
        fact, status, result.chunk.source, result.chunk.id,
        atom.literal, explanation,
        atom.start, atom.end,
        str(result.chunk.metadata["source_url"]),
    )


def validate_claim_facts(
    claim: str, evidence: list[SearchResult], *, as_of: date,
    entity_id: str | None = None, unit_id: str | None = None,
    requires_current_state: bool = False,
) -> FactValidation:
    """Analisa fatos explícitos sem alterar o pipeline decisório.

    Não faz NER geral, não infere que metadados estão verdadeiros nem aceita
    fatos atuais a partir da data de download da página.
    """
    facts = extract_explicit_facts(claim)
    if not facts:
        return FactValidation((), FactStatus.NOT_APPLICABLE)
    # Mesmo sem entidade fornecida, não misturar cursos conhecidos distintos.
    known = {
        str(item.chunk.metadata["entity_id"])
        for item in evidence if item.chunk.metadata.get("entity_id")
    }
    mentioned = explicitly_named_entities(claim, known)
    if entity_id and mentioned and any(
        normalize(identity) != normalize(entity_id) for identity in mentioned
    ):
        return FactValidation(
            tuple(FactCheck(fact, FactStatus.INSUFFICIENT_CONTEXT,
                explanation="Entidade explícita difere do escopo da pergunta") for fact in facts),
            FactStatus.INSUFFICIENT_CONTEXT,
        )
    scope = entity_id or (mentioned[0] if len(mentioned) == 1 else None)
    if scope is None and len(known) > 1:
        return FactValidation(
            tuple(FactCheck(fact, FactStatus.AMBIGUOUS,
                explanation="Múltiplas entidades nas fontes sem escopo identificável") for fact in facts),
            FactStatus.AMBIGUOUS,
        )
    checks = tuple(_check_one(
        fact, evidence, as_of=as_of, entity_id=scope, unit_id=unit_id,
        current=requires_current_state,
    ) for fact in facts[:12])
    if len(facts) > 12:
        return FactValidation(checks, FactStatus.AMBIGUOUS)
    priority = (
        FactStatus.VALUE_MISMATCH, FactStatus.AMBIGUOUS,
        FactStatus.INSUFFICIENT_CONTEXT, FactStatus.NO_ADMISSIBLE_SOURCE,
    )
    overall = next(
        (status for status in priority if any(item.status == status for item in checks)),
        FactStatus.VALUE_MATCH,
    )
    return FactValidation(checks, overall)
