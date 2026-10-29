"""Avaliação conservadora de afirmações factuais de uma resposta gerada.

A segmentação determinística por frase é um primeiro gate, não uma garantia
semântica de atomicidade: conjunções dentro de uma frase exigem testes adversariais.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from .grounding_decision import GroundingDecision, GroundingPolicy
from .models import SearchResult

MAX_CLAIMS = 8


class ClaimVerifier(Protocol):
    def support_score(self, query: str, passage: str) -> float: ...


@dataclass(frozen=True, slots=True)
class ClaimAssessment:
    claim: str
    decision: GroundingDecision
    source: str | None


@dataclass(frozen=True, slots=True)
class AnswerAssessment:
    decision: GroundingDecision
    claims: tuple[ClaimAssessment, ...]


def split_factual_claims(answer: str, *, max_claims: int = MAX_CLAIMS) -> tuple[str, ...]:
    """Divide frases e cláusulas separadas por ponto-e-vírgula; excesso falha fechado."""
    if max_claims <= 0:
        raise ValueError("max_claims deve ser positivo")
    # Divide também contraposições e conjunções que introduzem uma nova
    # oração com sujeito e verbo. Não divide enumerações simples.
    patterns = (
        r"(?<=[.!?;])\s+|(?<=;)(?=\S)|\n+"
        r"|,\s*(?=(?:mas|porém|contudo|entretanto)\b)"
        r"|\s+(?=(?:mas|porém|contudo|entretanto)\b)"
        r"|\s+e\s+(?=(?:o|a|os|as)\s+\w+(?:\s+\w+){0,3}\s+"
        r"(?:é|são|tem|têm|termina|terminam|começa|começam|funciona|"
        r"funcionam|fica|ficam|será|serão|encerra|encerram|custa|custam)\b)"
    )
    pieces = re.split("".join(patterns), answer.strip(), flags=re.IGNORECASE)
    claims = tuple(piece.strip() for piece in pieces if piece.strip())
    return claims if len(claims) <= max_claims else ()


def assess_answer(
    answer: str,
    evidence: list[SearchResult],
    verifier: ClaimVerifier,
    policy: GroundingPolicy,
) -> AnswerAssessment:
    claims = split_factual_claims(answer)
    if not claims:
        return AnswerAssessment(policy.decide(0.0), ())
    evaluations: list[ClaimAssessment] = []
    for claim in claims:
        best_score = 0.0
        source: str | None = None
        for result in evidence:
            score = verifier.support_score(claim, result.chunk.text)
            if score > best_score:
                best_score = score
                source = result.chunk.source
        evaluations.append(ClaimAssessment(claim, policy.decide(best_score), source))
    # O elo mais fraco determina a decisão. Uma frase não sustentada bloqueia o todo.
    return AnswerAssessment(
        policy.decide(min(item.decision.score for item in evaluations)),
        tuple(evaluations),
    )
