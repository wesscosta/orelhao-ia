from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

NLI_UNSUPPORTED_BELOW = 0.1250362694
NLI_SUPPORTED_AT_OR_ABOVE = 0.7557643056


class GroundingStatus(StrEnum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True, slots=True)
class GroundingDecision:
    status: GroundingStatus
    score: float

    @property
    def allows_response(self) -> bool:
        return self.status is GroundingStatus.SUPPORTED

    @property
    def should_abstain(self) -> bool:
        return not self.allows_response

    def as_dict(self) -> dict[str, str | float | bool]:
        return {
            "status": self.status.value,
            "score": self.score,
            "allows_response": self.allows_response,
            "should_abstain": self.should_abstain,
        }


@dataclass(frozen=True, slots=True)
class GroundingPolicy:
    unsupported_below: float = NLI_UNSUPPORTED_BELOW
    supported_at_or_above: float = NLI_SUPPORTED_AT_OR_ABOVE

    def __post_init__(self) -> None:
        if not 0.0 <= self.unsupported_below < self.supported_at_or_above <= 1.0:
            raise ValueError("thresholds de grounding devem ser ordenados entre 0 e 1")

    def decide(self, score: float) -> GroundingDecision:
        if not 0.0 <= score <= 1.0:
            raise ValueError("score de grounding deve estar entre 0 e 1")
        if score >= self.supported_at_or_above:
            status = GroundingStatus.SUPPORTED
        elif score < self.unsupported_below:
            status = GroundingStatus.UNSUPPORTED
        else:
            status = GroundingStatus.UNCERTAIN
        return GroundingDecision(status=status, score=score)

    def as_dict(self) -> dict[str, float | str]:
        return {
            "unsupported_below": self.unsupported_below,
            "supported_at_or_above": self.supported_at_or_above,
            "uncertain_range": "[unsupported_below, supported_at_or_above)",
        }


def summarize_grounding_scores(
    scores: Iterable[float],
    policy: GroundingPolicy | None = None,
) -> dict[str, int]:
    active_policy = policy or GroundingPolicy()
    summary = {status.value: 0 for status in GroundingStatus}
    for score in scores:
        decision = active_policy.decide(score)
        summary[decision.status.value] += 1
    return summary
