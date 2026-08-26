from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AbstentionReason(StrEnum):
    NO_RELEVANT_EVIDENCE = "no_relevant_evidence"
    SPECIFIC_INFORMATION_MISSING = "specific_information_missing"
    TEMPORAL_EVIDENCE_UNAVAILABLE = "temporal_evidence_unavailable"
    ENTITY_MISMATCH = "entity_mismatch"


_PT_BR_MESSAGES = {
    AbstentionReason.NO_RELEVANT_EVIDENCE: (
        "Não encontrei essa informação na minha base no momento."
    ),
    AbstentionReason.SPECIFIC_INFORMATION_MISSING: (
        "Encontrei informações relacionadas, mas não a resposta específica solicitada."
    ),
    AbstentionReason.TEMPORAL_EVIDENCE_UNAVAILABLE: (
        "Não tenho essa informação atualizada na minha base. Consulte um canal oficial."
    ),
    AbstentionReason.ENTITY_MISMATCH: (
        "Não encontrei essa informação para a unidade ou serviço solicitado."
    ),
}


@dataclass(frozen=True, slots=True)
class EvidenceDecision:
    answerable: bool
    reason: AbstentionReason | None = None

    def __post_init__(self) -> None:
        if self.answerable and self.reason is not None:
            raise ValueError("decisão respondível não deve declarar motivo de abstenção")
        if not self.answerable and self.reason is None:
            raise ValueError("decisão de abstenção deve declarar motivo")

    @classmethod
    def answer(cls) -> EvidenceDecision:
        return cls(answerable=True)

    @classmethod
    def abstain(cls, reason: AbstentionReason) -> EvidenceDecision:
        return cls(answerable=False, reason=reason)

    def message_pt_br(self) -> str | None:
        if self.reason is None:
            return None
        return _PT_BR_MESSAGES[self.reason]
