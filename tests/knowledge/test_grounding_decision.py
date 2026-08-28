from __future__ import annotations

import pytest

from orelhao.services.knowledge.grounding_decision import (
    NLI_SUPPORTED_AT_OR_ABOVE,
    NLI_UNSUPPORTED_BELOW,
    GroundingPolicy,
    GroundingStatus,
    summarize_grounding_scores,
)


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0.0, GroundingStatus.UNSUPPORTED),
        (NLI_UNSUPPORTED_BELOW - 1e-10, GroundingStatus.UNSUPPORTED),
        (NLI_UNSUPPORTED_BELOW, GroundingStatus.UNCERTAIN),
        (0.5, GroundingStatus.UNCERTAIN),
        (NLI_SUPPORTED_AT_OR_ABOVE - 1e-10, GroundingStatus.UNCERTAIN),
        (NLI_SUPPORTED_AT_OR_ABOVE, GroundingStatus.SUPPORTED),
        (1.0, GroundingStatus.SUPPORTED),
    ],
)
def test_grounding_policy_respects_frozen_boundaries(
    score: float,
    expected: GroundingStatus,
) -> None:
    decision = GroundingPolicy().decide(score)

    assert decision.status is expected
    assert decision.allows_response is (expected is GroundingStatus.SUPPORTED)
    assert decision.should_abstain is (expected is not GroundingStatus.SUPPORTED)


@pytest.mark.parametrize("score", [-0.1, 1.1])
def test_grounding_policy_rejects_invalid_score(score: float) -> None:
    with pytest.raises(ValueError, match="score de grounding"):
        GroundingPolicy().decide(score)


@pytest.mark.parametrize(
    ("lower", "upper"),
    [(-0.1, 0.8), (0.2, 1.1), (0.8, 0.8), (0.9, 0.8)],
)
def test_grounding_policy_rejects_invalid_thresholds(lower: float, upper: float) -> None:
    with pytest.raises(ValueError, match="thresholds de grounding"):
        GroundingPolicy(lower, upper)


def test_grounding_summary_counts_all_three_states() -> None:
    summary = summarize_grounding_scores([0.01, 0.2, 0.8, 0.9])

    assert summary == {"supported": 2, "unsupported": 1, "uncertain": 1}
