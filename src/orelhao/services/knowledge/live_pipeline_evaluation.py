"""Avaliação auditável do pipeline textual completo em perguntas reais de domínio.

Rótulos de fontes são provisórios até auditoria humana. A verificação automática
de termos é um filtro, não uma avaliação de factualidade semântica.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any

from .observation import GENERATION_ABSTENTION_MESSAGE, GroundingObservation


@dataclass(frozen=True, slots=True)
class LiveCase:
    case_id: str
    query: str
    expected_abstain: bool
    category: str
    required_terms: tuple[str, ...] = ()
    source: str | None = None


def load_live_cases(path: Path) -> tuple[str, list[LiveCase]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("cases"), list):
        raise TypeError("dataset deve conter objeto com lista cases")
    if payload.get("status") != "model-curated-not-human-adjudicated":
        raise ValueError("status de revisão esperado não foi declarado")
    cases: list[LiveCase] = []
    seen: set[str] = set()
    for item in payload["cases"]:
        if not isinstance(item, dict):
            raise TypeError("caso deve ser objeto")
        case_id, query, category = item.get("id"), item.get("query"), item.get("category")
        expected = item.get("expected_abstain")
        terms = item.get("required_terms")
        source = item.get("source")
        if not (
            isinstance(case_id, str) and case_id.strip()
            and isinstance(query, str) and query.strip()
            and isinstance(category, str) and category.strip()
            and isinstance(expected, bool)
            and isinstance(terms, list)
            and all(isinstance(t, str) and t.strip() for t in terms)
            and (source is None or isinstance(source, str))
        ):
            raise ValueError("campos de caso inválidos")
        if case_id in seen:
            raise ValueError("caso duplicado")
        if expected and terms:
            raise ValueError("abstenção não deve exigir termos de resposta")
        if not expected and (not terms or not source):
            raise ValueError("resposta positiva precisa de fonte e termos")
        seen.add(case_id)
        cases.append(LiveCase(case_id, query, expected, category, tuple(terms), source))
    if not cases:
        raise ValueError("dataset vazio")
    return str(payload.get("as_of", "")), cases


def normalize(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text.casefold())
    return re.sub(r"\s+", " ", "".join(c for c in plain if not unicodedata.combining(c)))


_REFUSAL = re.compile(
    r"\b(?:nao (?:encontrei|tenho|posso|ha (?:dados|evidencias))|"
    r"fontes divergentes|informac(?:ao|oes) (?:insuficientes|nao disponiveis))\b"
)


def assess_live_case(case: LiveCase, obs: GroundingObservation) -> dict[str, Any]:
    presented = normalize(obs.presented_answer)
    refusal = (
        obs.generation_skipped
        or obs.presented_answer == GENERATION_ABSTENTION_MESSAGE
        or bool(_REFUSAL.search(presented))
    )
    source_hit = case.source is None or any(ev.source == case.source for ev in obs.evidence)
    anchor_pass = (not refusal) and all(normalize(term) in presented for term in case.required_terms)
    false_allow = case.expected_abstain and not refusal
    false_block = not case.expected_abstain and refusal
    # Requer revisão humana mesmo se os anchors forem encontrados.
    result = {
        "id": case.case_id,
        "category": case.category,
        "query": case.query,
        "expected_abstain": case.expected_abstain,
        "predicted_abstain": refusal,
        "false_allow": bool(false_allow),
        "false_block": bool(false_block),
        "source_hit": source_hit,
        "text_anchor_pass": anchor_pass if not case.expected_abstain else None,
        "answerability_reason": (
            obs.answerability.decision.reason.value
            if obs.answerability and obs.answerability.decision.reason else None
        ),
        "precheck_verified_specific_answer": (
            obs.answerability.verified_specific_answer if obs.answerability else None
        ),
        "grounding_status": obs.grounding.status.value,
        "grounding_score": obs.grounding.score,
        "generation_skipped": obs.generation_skipped,
        "answer": obs.answer,
        "presented_answer": obs.presented_answer,
        "evidence_sources": [e.source for e in obs.evidence],
        "claim_assessments": [
            {
                "claim": claim.claim, "score": claim.decision.score,
                "source": claim.source, "chunk_id": claim.chunk_id,
            }
            for claim in obs.claims
        ],
        "latency": {
            "total_ms": obs.latency.total_ms,
            "retrieval_ms": obs.latency.retrieval_ms,
            "adjudication_ms": obs.latency.adjudication_ms,
            "generation_ms": obs.latency.generation_ms,
            "grounding_ms": obs.latency.grounding_ms,
        },
        "requires_human_review": True,
    }
    return result


def summarize_live_cases(results: list[dict[str, Any]]) -> dict[str, Any]:
    positive = [x for x in results if not x["expected_abstain"]]
    negative = [x for x in results if x["expected_abstain"]]
    fp = sum(x["false_allow"] for x in results)
    fn = sum(x["false_block"] for x in results)
    times = sorted(x["latency"]["total_ms"] for x in results if "latency" in x)
    return {
        "cases": len(results),
        "positive_cases": len(positive),
        "negative_cases": len(negative),
        "false_allow_cases": fp,
        "false_block_cases": fn,
        "false_allow_rate": fp / len(negative) if negative else None,
        "false_block_rate": fn / len(positive) if positive else None,
        "positive_anchor_pass": sum(x["text_anchor_pass"] is True for x in positive),
        "positive_source_hit": sum(x["source_hit"] for x in positive),
        "grounding_supported_with_bad_anchor": sum(
            x["grounding_status"] == "supported" and x["text_anchor_pass"] is False for x in positive
        ),
        "latency_p50_ms": median(times) if times else None,
        "latency_p95_ms": times[max(0, (len(times) * 95 + 99) // 100 - 1)] if times else None,
        "human_review_complete": False,
        "label_source": "model-curated, source-anchored; not independently human adjudicated",
    }
