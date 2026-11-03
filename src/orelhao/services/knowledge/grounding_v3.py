"""Grounding Decision V3: decisão conservadora sobre evidências já avaliadas.

Nenhum valor tipado, span lexical ou NLI uncertain pode elevar uma resposta
para ALLOW. Mismatch e ambiguidade podem apenas retirar permissões.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .fact_validation import FactStatus, FactValidation
from .grounding_decision import GroundingDecision, GroundingStatus


class V3Disposition(StrEnum):
    ALLOW = "allow"
    ABSTAIN = "abstain"
    CLARIFY = "clarify"


class V3Reason(StrEnum):
    PRECHECK_BLOCKED = "precheck_blocked"
    GENERATION_ABSTAINED = "generation_abstained"
    ENTITY_MISMATCH = "entity_mismatch"
    FACT_MISMATCH = "fact_mismatch"
    FACT_AMBIGUOUS = "fact_ambiguous"
    FACT_INSUFFICIENT = "fact_insufficient"
    REQUESTED_ATTRIBUTE_MISSING = "requested_attribute_missing"
    NLI_UNCERTAIN = "nli_uncertain"
    NLI_UNSUPPORTED = "nli_unsupported"
    SUPPORTED = "supported"
    LOCAL_CLOCK = "local_clock"


_MESSAGES: dict[V3Reason, str] = {
    V3Reason.ENTITY_MISMATCH: (
        "A resposta encontrada não corresponde à unidade ou ao curso solicitado. "
        "Consulte um canal oficial para confirmar."
    ),
    V3Reason.FACT_MISMATCH: (
        "Encontrei valores divergentes dos documentos oficiais. "
        "Não consigo confirmar essa resposta com segurança."
    ),
    V3Reason.FACT_AMBIGUOUS: (
        "Encontrei informações de ofertas diferentes. "
        "Informe a unidade ou turma para esclarecer."
    ),
    V3Reason.FACT_INSUFFICIENT: (
        "Não encontrei uma fonte válida que confirme todos os dados dessa resposta."
    ),
    V3Reason.REQUESTED_ATTRIBUTE_MISSING: (
        "Encontrei informações relacionadas, mas não o dado específico solicitado."
    ),
}


@dataclass(frozen=True, slots=True)
class GroundingV3Decision:
    disposition: V3Disposition
    reason: V3Reason
    nli_status: GroundingStatus
    nli_score: float
    fact_statuses: tuple[str, ...] = ()
    supporting_chunk_ids: tuple[str, ...] = ()
    enforced: bool = False

    @property
    def allows_response(self) -> bool:
        return self.disposition is V3Disposition.ALLOW

    @property
    def should_abstain(self) -> bool:
        return not self.allows_response

    @property
    def safe_message(self) -> str | None:
        return _MESSAGES.get(self.reason)

    def as_dict(self) -> dict[str, object]:
        return {
            "disposition": self.disposition.value,
            "reason": self.reason.value,
            "nli_status": self.nli_status.value,
            "nli_score": (
                None if self.nli_status is GroundingStatus.NOT_APPLICABLE
                else self.nli_score
            ),
            "fact_statuses": list(self.fact_statuses),
            "supporting_chunk_ids": list(self.supporting_chunk_ids),
            "allows_response": self.allows_response,
            "should_abstain": self.should_abstain,
            "enforced": self.enforced,
        }


def decide_grounding_v3(
    nli: GroundingDecision,
    fact_validations: tuple[FactValidation, ...],
    *,
    precheck_blocked: bool = False,
    generation_abstained: bool = False,
    entity_mismatch: bool = False,
    requested_attribute_missing: bool = False,
    enforce: bool = False,
) -> GroundingV3Decision:
    """Veto only: no factual match may upgrade NLI UNCERTAIN to ALLOW.

    Precedence: precheck > refusal > entity > factual mismatch > ambiguity
    > incomplete factual evidence > NLI. All claims must be checked.
    """
    statuses = tuple(check.status.value for check in fact_validations)
    chunk_ids = tuple(sorted({
        check.chunk_id for assessment in fact_validations
        for check in assessment.checks
        if check.status is FactStatus.VALUE_MATCH and check.chunk_id is not None
    }))
    reason: V3Reason
    disposition = V3Disposition.ABSTAIN

    if precheck_blocked:
        reason = V3Reason.PRECHECK_BLOCKED
    elif generation_abstained:
        reason = V3Reason.GENERATION_ABSTAINED
    elif entity_mismatch:
        reason = V3Reason.ENTITY_MISMATCH
    elif requested_attribute_missing:
        reason = V3Reason.REQUESTED_ATTRIBUTE_MISSING
    elif FactStatus.VALUE_MISMATCH.value in statuses:
        reason = V3Reason.FACT_MISMATCH
    elif FactStatus.AMBIGUOUS.value in statuses:
        reason, disposition = V3Reason.FACT_AMBIGUOUS, V3Disposition.CLARIFY
    elif any(x in statuses for x in (
        FactStatus.INSUFFICIENT_CONTEXT.value,
        FactStatus.NO_ADMISSIBLE_SOURCE.value,
    )):
        reason = V3Reason.FACT_INSUFFICIENT
    elif nli.status is GroundingStatus.UNSUPPORTED:
        reason = V3Reason.NLI_UNSUPPORTED
    elif nli.status is GroundingStatus.UNCERTAIN:
        reason = V3Reason.NLI_UNCERTAIN
    else:
        reason, disposition = V3Reason.SUPPORTED, V3Disposition.ALLOW
    return GroundingV3Decision(
        disposition, reason, nli.status, nli.score, statuses, chunk_ids, enforce
    )
