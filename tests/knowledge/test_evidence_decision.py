from __future__ import annotations

import pytest

from orelhao.services.knowledge.evidence_decision import (
    AbstentionReason,
    EvidenceDecision,
)


@pytest.mark.parametrize(
    ("reason", "expected_fragment"),
    [
        (AbstentionReason.NO_RELEVANT_EVIDENCE, "minha base"),
        (AbstentionReason.SPECIFIC_INFORMATION_MISSING, "resposta específica"),
        (AbstentionReason.TEMPORAL_EVIDENCE_UNAVAILABLE, "atualizada"),
        (AbstentionReason.ENTITY_MISMATCH, "unidade ou serviço"),
    ],
)
def test_abstention_decision_exposes_safe_pt_br_message(
    reason: AbstentionReason,
    expected_fragment: str,
) -> None:
    decision = EvidenceDecision.abstain(reason)

    assert not decision.answerable
    assert expected_fragment in (decision.message_pt_br() or "")


def test_answerable_decision_has_no_abstention_message() -> None:
    decision = EvidenceDecision.answer()

    assert decision.answerable
    assert decision.reason is None
    assert decision.message_pt_br() is None


def test_evidence_decision_rejects_inconsistent_state() -> None:
    with pytest.raises(ValueError, match="respondível"):
        EvidenceDecision(True, AbstentionReason.NO_RELEVANT_EVIDENCE)
    with pytest.raises(ValueError, match="deve declarar"):
        EvidenceDecision(False)
