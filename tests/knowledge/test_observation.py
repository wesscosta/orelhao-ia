import json
from pathlib import Path

from orelhao.services.knowledge.models import Chunk, SearchResult
from orelhao.services.knowledge.observation import (
    GENERATION_ABSTENTION_MESSAGE,
    ExtractivePreviewAnswerGenerator,
    LocalLLMAnswerGenerator,
    ObservationLog,
    ObservationWorkbench,
)
from orelhao.services.llm.service import INSUFFICIENT_CONTEXT
from orelhao.services.rag.retriever import RetrievedContext


class StubRetriever:
    def search(self, query: str, *, limit: int = 4) -> list[SearchResult]:
        del query, limit
        return [
            SearchResult(
                Chunk("faq:0", "faq", "O atendimento funciona de segunda a sexta.", "faq.md", 0),
                0.82,
            )
        ]


class StubGenerator:
    def generate(self, question: str, evidence: list[SearchResult]) -> str:
        del question, evidence
        return "O atendimento funciona de segunda a sexta."


class StubVerifier:
    def __init__(self, score: float) -> None:
        self.score = score

    def support_score(self, query: str, passage: str) -> float:
        assert query == "O atendimento funciona de segunda a sexta."
        assert "segunda a sexta" in passage
        return self.score


def test_workbench_observes_without_blocking_answer(tmp_path: Path) -> None:
    log = ObservationLog(tmp_path / "grounding.jsonl")
    workbench = ObservationWorkbench(
        StubRetriever(), StubGenerator(), StubVerifier(0.01), log
    )

    result = workbench.observe("Quando funciona o atendimento?")

    assert result.grounding.status == "unsupported"
    assert result.grounding.should_abstain
    assert result.presented_answer == result.answer
    assert result.mode == "observe"
    assert result.latency.total_ms >= 0
    payload = json.loads(log.path.read_text(encoding="utf-8"))
    assert payload["event"] == "observation"
    assert payload["presented_answer"] == result.answer


def test_observation_log_appends_human_rating(tmp_path: Path) -> None:
    log = ObservationLog(tmp_path / "grounding.jsonl")
    diagnostic = log.append_rating(
        "abc123", "partial", grounding_status="supported"
    )

    payload = json.loads(log.path.read_text(encoding="utf-8"))
    assert payload["event"] == "human_rating"
    assert payload["observation_id"] == "abc123"
    assert payload["rating"] == "partial"
    assert diagnostic == "possible_false_positive"
    assert payload["diagnostic"] == "possible_false_positive"


def test_extractive_preview_is_short_plain_text_and_prefers_location() -> None:
    generator = ExtractivePreviewAnswerGenerator()
    evidence = [
        SearchResult(
            Chunk(
                "about:0", "about", "# História\n\nO Senac promove educação profissional no Piauí.", "about.md", 0
            ),
            0.8,
        ),
        SearchResult(
            Chunk(
                "units:0", "units", "# Unidades\n\nHá unidades em Teresina, Parnaíba e Picos.", "units.md", 0
            ),
            0.7,
        ),
    ]

    answer = generator.generate("Onde tem unidade do Senac no Piauí?", evidence)

    assert "Teresina, Parnaíba e Picos" in answer
    assert "#" not in answer
    assert len(answer) <= 360


class InsufficientLLM:
    def generate(self, query: str, context: list[RetrievedContext]) -> str:
        del query, context
        return INSUFFICIENT_CONTEXT


def test_local_llm_generator_translates_insufficient_context() -> None:
    generator = LocalLLMAnswerGenerator(InsufficientLLM())

    assert generator.generate("Pergunta", []) == GENERATION_ABSTENTION_MESSAGE
