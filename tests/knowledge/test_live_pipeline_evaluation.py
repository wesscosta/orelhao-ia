import json
from pathlib import Path

import pytest

from orelhao.services.knowledge.grounding_decision import GroundingPolicy
from orelhao.services.knowledge.live_pipeline_evaluation import (
    LiveCase,
    assess_live_case,
    load_live_cases,
    normalize,
    summarize_live_cases,
)
from orelhao.services.knowledge.observation import GroundingObservation, ObservationLatency

ROOT = Path(__file__).resolve().parents[2]


def observation(text: str, *, skipped: bool = False) -> GroundingObservation:
    return GroundingObservation(
        observation_id="abc",
        created_at="2026-10-29T12:00:00Z",
        question="Pergunta?",
        answer=text,
        presented_answer=text,
        evidence=(),
        grounding=GroundingPolicy().decide(0.97),
        claims=(),
        latency=ObservationLatency(1, 1, 1, 3),
        generator="stub",
        generation_abstained=skipped,
        generation_skipped=skipped,
    )


def test_real_case_sources_and_anchors_exist() -> None:
    from orelhao.services.knowledge.loader import load_documents

    _, cases = load_live_cases(ROOT / "knowledge/evaluation/grounding-real-senac-pi-v1.json")
    docs = {d.source: d for d in load_documents(ROOT / "knowledge/sources")}
    assert len(cases) == 40
    assert sum(c.expected_abstain for c in cases) == 20
    assert len({c.case_id for c in cases}) == 40
    for case in cases:
        if case.source:
            assert case.source in docs
            assert all(normalize(t) in normalize(docs[case.source].text) for t in case.required_terms)


def test_real_case_flags_false_allow_and_false_block() -> None:
    negative = LiveCase("n", "Há vagas agora?", True, "temporal")
    positive = LiveCase("p", "Qual o horário?", False, "schedule", ("18h",), "source.md")
    allow = assess_live_case(negative, observation("O horário é 18h."))
    block = assess_live_case(positive, observation("Não encontrei essa informação."))
    assert allow["false_allow"]
    assert block["false_block"]
    summary = summarize_live_cases([allow, block])
    assert summary["false_allow_rate"] == 1
    assert summary["false_block_rate"] == 1
    assert not summary["human_review_complete"]


def test_real_case_load_rejects_duplicate_ids(tmp_path: Path) -> None:
    payload = json.loads((ROOT / "knowledge/evaluation/grounding-real-senac-pi-v1.json").read_text())
    payload["cases"] = [payload["cases"][0], payload["cases"][0]]
    file = tmp_path / "duplicate.json"
    file.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="duplicado"):
        load_live_cases(file)
