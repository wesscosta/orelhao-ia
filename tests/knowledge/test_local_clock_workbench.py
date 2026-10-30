from __future__ import annotations

import json
from pathlib import Path

import pytest

from orelhao.services.knowledge.observation import (
    GENERATION_ABSTENTION_MESSAGE,
    LocalLLMAnswerGenerator,
    ObservationLog,
    ObservationWorkbench,
)
from orelhao.services.llm.abstention import INSUFFICIENT_CONTEXT, normalize_abstention
from orelhao.services.rag.retriever import RetrievedContext


class CountingRetriever:
    calls = 0

    def search(self, query: str, *, limit: int = 8) -> list[object]:
        self.calls += 1
        return []


class CountingGenerator:
    calls = 0

    def generate(self, question: str, evidence: list[object]) -> str:
        self.calls += 1
        return "Este texto não deve ser gerado."


class CountingNLI:
    calls = 0

    def support_score(self, query: str, passage: str) -> float:
        self.calls += 1
        return 0.99


@pytest.mark.parametrize("mode", ["observe", "enforce"])
def test_clock_skips_all_knowledge_and_llm_and_is_speakable(
    tmp_path: Path, mode: str,
) -> None:
    r, g, n = CountingRetriever(), CountingGenerator(), CountingNLI()
    log = ObservationLog(tmp_path / "events.jsonl")
    bench = ObservationWorkbench(r, g, n, log, mode=mode)
    a = bench.observe("Que dia é hoje? Que horas são agora?")
    assert a.answer_origin == "local_clock"
    assert a.generator == "LocalClockService"
    assert a.generation_skipped
    assert a.presented_answer == a.answer
    assert "Hoje é" in a.answer and "Agora são" in a.answer
    assert a.answerability is None
    assert a.evidence == a.claims == a.fact_validations == ()
    assert a.grounding_v3 is not None
    assert a.grounding_v3.disposition.value == "allow"
    assert a.grounding_v3.reason.value == "local_clock"
    assert a.grounding_v3.enforced == (mode == "enforce")
    assert r.calls == g.calls == n.calls == 0
    assert log.presented_answer_for(a.observation_id) == a.answer
    payload = json.loads(log.path.read_text())
    assert payload["answer_origin"] == "local_clock"
    assert payload["grounding"]["status"] == "not_applicable"
    assert payload["grounding"]["score"] is None
    assert payload["grounding_v3"]["nli_score"] is None
    assert payload["local_clock"]["timezone"] == "America/Fortaleza"
    assert payload["local_clock"]["timestamp"].endswith("-03:00")


def test_institutional_question_remains_in_rag(tmp_path: Path) -> None:
    r, g, n = CountingRetriever(), CountingGenerator(), CountingNLI()
    bench = ObservationWorkbench(
        r, g, n, ObservationLog(tmp_path / "institutional.jsonl"),
    )
    observation = bench.observe("Há vagas disponíveis hoje?")
    assert observation.answer_origin == "rag"
    assert r.calls == g.calls == 1


@pytest.mark.parametrize("raw", [
    "INSUFFICIENT CONTEXT " * 12 + "INSUFFICIENT",
    "INSUFFICIENT CONTEXT INSUFFICIENT CONTEXT",
    "INSUFFICIENT_CONTEXT INSUFFICIENT_CONTEXT",
    "Insufficient Context!",
])
def test_normalizes_repeated_marker_without_reading_it(raw: str) -> None:
    assert normalize_abstention(raw) == INSUFFICIENT_CONTEXT

    class RepeatingLLM:
        def generate(self, query: str, context: list[RetrievedContext]) -> str:
            return raw

    generator = LocalLLMAnswerGenerator(RepeatingLLM())
    assert generator.generate("Que dia é hoje?", []) == GENERATION_ABSTENTION_MESSAGE


def test_refusal_does_not_consume_mixed_factual_answer() -> None:
    response = "INSUFFICIENT CONTEXT Mas o curso tem 30 horas."
    assert normalize_abstention(response) == response



def test_old_logged_repeated_marker_is_not_synthesized(tmp_path: Path) -> None:
    path = tmp_path / "history.jsonl"
    old_id = "a" * 32
    path.write_text(json.dumps({
        "event": "observation",
        "observation_id": old_id,
        "presented_answer": "INSUFFICIENT CONTEXT " * 12 + "INSUFFICIENT",
    }) + "\n")
    log = ObservationLog(path)
    assert log.presented_answer_for(old_id) == GENERATION_ABSTENTION_MESSAGE
