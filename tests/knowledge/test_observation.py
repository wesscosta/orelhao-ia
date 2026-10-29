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


class TwoClaimGenerator:
    def generate(self, question: str, evidence: list[SearchResult]) -> str:
        del question, evidence
        return "O atendimento funciona de segunda a sexta. Inscrições encerram amanhã."


class SelectiveVerifier:
    def support_score(self, query: str, passage: str) -> float:
        del passage
        return 0.9 if query.startswith("O atendimento") else 0.01


def test_workbench_enforce_blocks_unverified_second_claim(tmp_path: Path) -> None:
    log = ObservationLog(tmp_path / "strict.jsonl")
    workbench = ObservationWorkbench(
        StubRetriever(), TwoClaimGenerator(), SelectiveVerifier(), log, mode="enforce"
    )
    observed = workbench.observe("Qual é o atendimento e a data?")
    assert len(observed.claims) == 2
    assert observed.answer.endswith("amanhã.")
    assert observed.grounding.should_abstain
    assert observed.presented_answer == GENERATION_ABSTENTION_MESSAGE
    assert observed.mode == "enforce"
    payload = json.loads(log.path.read_text(encoding="utf-8"))
    assert len(payload["claims"]) == 2
    assert payload["presented_answer"] == GENERATION_ABSTENTION_MESSAGE
    assert payload["answer"] != payload["presented_answer"]


def test_workbench_rejects_unknown_mode(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(ValueError, match="mode"):
        ObservationWorkbench(
            StubRetriever(), StubGenerator(), StubVerifier(0.8),
            ObservationLog(tmp_path / "test.jsonl"), mode="unsafe"
        )


class LongAnswerLLM:
    def generate(self, query: str, context: list[RetrievedContext]) -> str:
        del query, context
        return (
            "O balcão atende de segunda a sexta. "
            "O documento deve ter fotografia. "
            + "Informação muito extensa " * 26
            + "e ainda pode continuar"
        )


def test_llm_generator_does_not_cut_incomplete_sentence() -> None:
    generator = LocalLLMAnswerGenerator(LongAnswerLLM())
    answer = generator.generate(
        "Pergunta",
        [SearchResult(Chunk("id", "title", "Fonte.", "faq.md", 0), 0.9)],
    )
    assert answer == "O balcão atende de segunda a sexta. O documento deve ter fotografia."
    assert len(answer) <= 360



class CountingGenerator:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, question: str, evidence: list[SearchResult]) -> str:
        self.calls += 1
        return "Há vagas hoje."


def test_enforce_precheck_skips_llm_for_temporal_question(tmp_path: Path) -> None:
    from orelhao.services.knowledge.answerability import EvidenceAdjudicator

    generator = CountingGenerator()
    log = ObservationLog(tmp_path / "grounding.jsonl")
    bench = ObservationWorkbench(
        StubRetriever(), generator, StubVerifier(0.9), log,
        mode="enforce", adjudicator=EvidenceAdjudicator(),
    )
    observation = bench.observe("Há vagas hoje?")
    assert observation.generation_skipped
    assert generator.calls == 0
    assert observation.answerability is not None
    assert not observation.answerability.decision.answerable
    assert observation.presented_answer == observation.answer
    data = json.loads(log.path.read_text())
    assert data["answerability"]["reason"] == "temporal_evidence_unavailable"
    assert data["generation_skipped"]


def test_observe_precheck_preserves_diagnostic_llm_generation(tmp_path: Path) -> None:
    from orelhao.services.knowledge.answerability import EvidenceAdjudicator

    generator = CountingGenerator()

    class PermissiveVerifier:
        def support_score(self, query: str, passage: str) -> float:
            return 0.1

    bench = ObservationWorkbench(
        StubRetriever(), generator, PermissiveVerifier(),
        ObservationLog(tmp_path / "log.jsonl"),
        adjudicator=EvidenceAdjudicator(),
    )
    observation = bench.observe("Há vagas hoje?")
    assert generator.calls == 1
    assert not observation.generation_skipped
    assert observation.answerability is not None
    assert not observation.answerability.decision.answerable
    assert observation.presented_answer == "Há vagas hoje."



class AlwaysEntailedVerifier:
    def support_score(self, query: str, passage: str) -> float:
        return 0.99


class ExcelSourceRetriever:
    def search(self, query: str, *, limit: int = 4) -> list[SearchResult]:
        del query, limit
        return [
            SearchResult(Chunk(
                "advanced:0", "advanced", "Excel Avançado: 60 horas.", "advanced.md",
                0, {"entity_id": "curso:excel avancado"},
            ), 0.9),
            SearchResult(Chunk(
                "excel:0", "excel", "Excel: 30 horas.", "excel.md",
                0, {"entity_id": "curso:excel"},
            ), 0.8),
        ]


class WrongNamedEntityGenerator:
    def __init__(self) -> None:
        self.used_sources: list[str] = []

    def generate(self, question: str, evidence: list[SearchResult]) -> str:
        del question
        self.used_sources = [result.chunk.source for result in evidence]
        return "Excel Avançado tem 60 horas."


def test_enforce_does_not_trust_nli_for_wrong_named_entity(tmp_path: Path) -> None:
    from orelhao.services.knowledge.answerability import EvidenceAdjudicator

    generator = WrongNamedEntityGenerator()
    bench = ObservationWorkbench(
        ExcelSourceRetriever(), generator, AlwaysEntailedVerifier(),
        ObservationLog(tmp_path / "observations.jsonl"),
        adjudicator=EvidenceAdjudicator(),
    )
    result = bench.observe("Qual a carga horária de Excel?", mode="enforce")
    assert generator.used_sources == ["excel.md"]
    assert result.answer_entity_mismatch
    assert result.grounding.should_abstain
    assert result.presented_answer == GENERATION_ABSTENTION_MESSAGE
    assert result.answerability is not None
    assert result.answerability.constraints.entity_id == "curso:excel"
