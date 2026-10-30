"""Contratos e precedência do Grounding Decision V3."""
from __future__ import annotations

from orelhao.services.knowledge.fact_extraction import ExtractedFact, FactKind
from orelhao.services.knowledge.fact_validation import FactCheck, FactStatus, FactValidation
from orelhao.services.knowledge.grounding_decision import GroundingPolicy
from orelhao.services.knowledge.grounding_v3 import (
    V3Disposition,
    V3Reason,
    decide_grounding_v3,
)


def fact(status: FactStatus, *, chunk_id: str | None = "doc:0") -> FactValidation:
    return FactValidation(
        (
            FactCheck(
                ExtractedFact(FactKind.DURATION, "60", "hours", 0, 8, "60 horas"),
                status,
                source="doc.md" if chunk_id else None,
                chunk_id=chunk_id,
            ),
        ),
        status,
    )


def test_value_match_never_overrides_uncertain_or_unsupported_nli() -> None:
    policy = GroundingPolicy()
    for score in (0.1, 0.5):
        decision = decide_grounding_v3(
            policy.decide(score), (fact(FactStatus.VALUE_MATCH),), enforce=True
        )
        assert decision.disposition is V3Disposition.ABSTAIN
        assert decision.reason in (V3Reason.NLI_UNCERTAIN, V3Reason.NLI_UNSUPPORTED)
        assert not decision.allows_response
        assert decision.fact_statuses == ("value_match",)


def test_supported_nli_and_matching_fact_can_allow_with_provenance() -> None:
    decision = decide_grounding_v3(
        GroundingPolicy().decide(0.95), (fact(FactStatus.VALUE_MATCH),),
        enforce=True,
    )
    assert decision.reason is V3Reason.SUPPORTED
    assert decision.allows_response
    assert decision.supporting_chunk_ids == ("doc:0",)
    assert decision.as_dict()["enforced"] is True


def test_one_wrong_fact_vetoes_supported_nli_and_other_matches() -> None:
    decision = decide_grounding_v3(
        GroundingPolicy().decide(0.999),
        (fact(FactStatus.VALUE_MATCH), fact(FactStatus.VALUE_MISMATCH)),
        enforce=True,
    )
    assert decision.reason is V3Reason.FACT_MISMATCH
    assert decision.disposition is V3Disposition.ABSTAIN
    assert decision.safe_message is not None
    assert "valores divergentes" in decision.safe_message


def test_ambiguous_offers_clarify_without_relaxing_nli() -> None:
    decision = decide_grounding_v3(
        GroundingPolicy().decide(0.9), (fact(FactStatus.AMBIGUOUS),)
    )
    assert decision.reason is V3Reason.FACT_AMBIGUOUS
    assert decision.disposition is V3Disposition.CLARIFY
    assert not decision.allows_response
    assert "unidade ou turma" in (decision.safe_message or "")


def test_missing_or_invalid_provenance_blocks_numeric_answers() -> None:
    for status in (FactStatus.NO_ADMISSIBLE_SOURCE, FactStatus.INSUFFICIENT_CONTEXT):
        decision = decide_grounding_v3(
            GroundingPolicy().decide(0.98), (fact(status, chunk_id=None),)
        )
        assert decision.disposition is V3Disposition.ABSTAIN
        assert decision.reason is V3Reason.FACT_INSUFFICIENT


def test_precheck_and_entity_restrictions_take_precedence() -> None:
    policy = GroundingPolicy()
    result = decide_grounding_v3(
        policy.decide(0.9), (fact(FactStatus.VALUE_MISMATCH),),
        precheck_blocked=True, entity_mismatch=True, enforce=True,
    )
    assert result.reason is V3Reason.PRECHECK_BLOCKED
    result = decide_grounding_v3(
        policy.decide(0.9), (fact(FactStatus.VALUE_MISMATCH),),
        entity_mismatch=True,
    )
    assert result.reason is V3Reason.ENTITY_MISMATCH


def test_generation_abstention_is_not_promoted_by_matching_facts() -> None:
    decision = decide_grounding_v3(
        GroundingPolicy().decide(0.9), (fact(FactStatus.VALUE_MATCH),),
        generation_abstained=True,
    )
    assert decision.reason is V3Reason.GENERATION_ABSTAINED
    assert not decision.allows_response


def test_no_typed_values_preserves_previous_nli_decision() -> None:
    for score in (0.01, 0.5, 0.9):
        legacy = GroundingPolicy().decide(score)
        result = decide_grounding_v3(
            legacy, (FactValidation((), FactStatus.NOT_APPLICABLE),)
        )
        assert result.allows_response == legacy.allows_response
        assert result.nli_score == score


def test_default_policy_assesses_but_does_not_claim_enforcement() -> None:
    result = decide_grounding_v3(
        GroundingPolicy().decide(0.99), (fact(FactStatus.VALUE_MISMATCH),)
    )
    assert result.as_dict()["enforced"] is False
