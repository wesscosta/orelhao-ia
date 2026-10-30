"""Integração ponta a ponta textual: NLI, facts, precheck e resposta apresentada."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from orelhao.services.knowledge.answerability import EvidenceAdjudicator
from orelhao.services.knowledge.grounding_v3 import V3Disposition, V3Reason
from orelhao.services.knowledge.live_pipeline_evaluation import LiveCase, assess_live_case
from orelhao.services.knowledge.models import Chunk, SearchResult
from orelhao.services.knowledge.observation import (
    ObservationLog,
    ObservationWorkbench,
)


class Retriever:
    def __init__(self, text: str, **meta: object) -> None:
        metadata: dict[str, object] = {
            "authority": "primary",
            "source_url": "https://example.org/informacoes",
        }
        metadata.update(meta)
        self.chunks = [SearchResult(
            Chunk("official:0", "official", text, "official.md", 0, metadata),
            0.98,
        )]

    def search(self, query: str, *, limit: int = 8) -> list[SearchResult]:
        del query
        return self.chunks[:limit]


class Generator:
    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.calls = 0

    def generate(self, question: str, evidence: list[SearchResult]) -> str:
        del question, evidence
        self.calls += 1
        return self.answer


class NLI:
    def __init__(self, score: float) -> None:
        self.score = score

    def support_score(self, query: str, passage: str) -> float:
        del query, passage
        return self.score


def bench(
    tmp_path: Path, text: str, answer: str, score: float = 0.99,
    *, mode: str = "enforce", adjudicator: bool = False, **metadata: object,
) -> tuple[ObservationWorkbench, Generator, ObservationLog]:
    log = ObservationLog(tmp_path / "grounding-v3.jsonl")
    generator = Generator(answer)
    instance = ObservationWorkbench(
        Retriever(text, **metadata), generator, NLI(score), log,
        mode=mode,
        adjudicator=EvidenceAdjudicator() if adjudicator else None,
    )
    return instance, generator, log


def test_wrong_duration_is_never_spoken_even_when_nli_is_099(tmp_path: Path) -> None:
    workbench, _, log = bench(
        tmp_path, "Excel tem 30 horas.", "Excel tem 60 horas.",
        entity_id="curso:excel",
    )
    result = workbench.observe("Qual a carga horária de Excel?")
    assert result.grounding.allows_response
    assert result.grounding_v3 is not None
    assert result.grounding_v3.reason is V3Reason.FACT_MISMATCH
    assert result.presented_answer != result.answer
    assert "60 horas" not in result.presented_answer
    payload = json.loads(log.path.read_text())
    assert payload["grounding_v3"]["disposition"] == "abstain"
    assert payload["grounding_v3"]["enforced"]
    assert log.presented_answer_for(result.observation_id) == result.presented_answer


def test_span_match_does_not_override_uncertain_nli(tmp_path: Path) -> None:
    workbench, _, _ = bench(
        tmp_path, "Excel tem 30 horas.", "Excel tem 30 horas.", 0.54,
    )
    result = workbench.observe("Qual a duração?")
    assert result.fact_validations[0].status.value == "value_match"
    assert result.grounding_v3 is not None
    assert result.grounding_v3.reason is V3Reason.NLI_UNCERTAIN
    assert result.presented_answer != result.answer


def test_multiple_course_durations_request_clarification(tmp_path: Path) -> None:
    workbench, _, _ = bench(
        tmp_path, "Informática Básica: 80 horas ou 140 horas.",
        "Informática Básica tem 80 horas.",
        entity_id="curso:informatica basica",
    )
    result = workbench.observe("Qual a duração de Informática Básica?")
    assert result.grounding_v3 is not None
    assert result.grounding_v3.disposition is V3Disposition.CLARIFY
    assert "unidade ou turma" in result.presented_answer


def test_current_price_from_old_download_fails_closed(tmp_path: Path) -> None:
    workbench, _, _ = bench(
        tmp_path, "Preço do curso R$ 242,00.",
        "O preço atual é R$ 242,00.",
        adjudicator=True, retrieved_at="2026-10-29",
        entity_id="curso:excel",
    )
    result = workbench.observe("Qual é o preço atual do curso Excel?")
    assert result.answerability is not None
    assert result.answerability.decision.answerable is False
    assert result.generation_skipped
    assert result.grounding_v3 is not None
    assert result.grounding_v3.reason is V3Reason.PRECHECK_BLOCKED


def test_observe_preserves_original_answer_and_logs_veto(tmp_path: Path) -> None:
    workbench, _, log = bench(
        tmp_path, "Excel: 30 horas.", "Excel: 60 horas.", mode="observe"
    )
    result = workbench.observe("Quantas horas tem Excel?")
    assert result.presented_answer == result.answer
    assert result.grounding_v3 is not None
    assert result.grounding_v3.reason is V3Reason.FACT_MISMATCH
    payload = json.loads(log.path.read_text())
    assert payload["grounding_v3"]["enforced"] is False


@pytest.mark.parametrize("answer,expected", [
    ("O prazo é 15 dias corridos.", V3Reason.FACT_MISMATCH),
    ("O prazo é 15 dias úteis.", V3Reason.SUPPORTED),
])
def test_deadline_unit_comparison_in_pipeline(
    tmp_path: Path, answer: str, expected: V3Reason,
) -> None:
    workbench, _, _ = bench(
        tmp_path, "A Ouvidoria responde em 15 dias úteis.", answer
    )
    result = workbench.observe("Qual o prazo de resposta?")
    assert result.grounding_v3 is not None
    assert result.grounding_v3.reason is expected


def test_v3_clarify_is_recognized_as_refusal_by_evaluation(tmp_path: Path) -> None:
    workbench, _, _ = bench(
        tmp_path, "Informática Básica tem 80 horas e 140 horas.",
        "O curso Informática Básica tem 80 horas.",
        entity_id="curso:informatica basica",
    )
    obs = workbench.observe("Qual a carga horária?")
    case = LiveCase("P1", "Qual a carga horária?", True, "ambiguous")
    result = assess_live_case(case, obs)
    assert result["predicted_abstain"] is True
    assert result["false_allow"] is False
    assert result["grounding_v3"]["reason"] == "fact_ambiguous"



def test_capacity_question_cannot_pass_with_only_true_but_irrelevant_claim(
    tmp_path: Path,
) -> None:
    workbench, _, _ = bench(
        tmp_path,
        "A biblioteca de Picos é destinada aos alunos, instrutores e colaboradores.",
        "A biblioteca de Picos atende alunos, instrutores e colaboradores.",
        0.99,
    )
    observed = workbench.observe("Qual a lotação máxima da biblioteca de Picos?")
    assert observed.grounding.allows_response
    assert observed.grounding_v3 is not None
    assert observed.grounding_v3.reason is V3Reason.REQUESTED_ATTRIBUTE_MISSING
    assert observed.presented_answer != observed.answer


def test_capacity_answer_needs_value_and_verified_primary_evidence(
    tmp_path: Path,
) -> None:
    valid, _, _ = bench(
        tmp_path,
        "A lotação máxima da biblioteca é 40 pessoas.",
        "A lotação máxima é 40 pessoas.",
    )
    yes = valid.observe("Qual a lotação máxima da biblioteca?")
    assert yes.grounding_v3 is not None
    assert yes.grounding_v3.disposition is V3Disposition.ALLOW
    no, _, _ = bench(
        tmp_path,
        "A lotação máxima da biblioteca é 40 pessoas.",
        "A lotação máxima é 50 pessoas.",
    )
    fail = no.observe("Qual a lotação máxima da biblioteca?")
    assert fail.grounding_v3 is not None
    assert fail.grounding_v3.reason is V3Reason.FACT_MISMATCH


def test_requested_attribute_check_ignores_unrelated_general_questions() -> None:
    from orelhao.services.knowledge.answer_requirements import (
        missing_requested_fact,
    )
    assert missing_requested_fact(
        "Qual a lotação máxima da biblioteca?", "O acesso é para alunos."
    )
    assert not missing_requested_fact(
        "Quem pode usar a biblioteca?", "O acesso é para alunos."
    )
    assert missing_requested_fact(
        "Qual o telefone do Senac?", "A unidade atende de segunda a sexta."
    )
    assert not missing_requested_fact(
        "Qual a lotação máxima da biblioteca?", "A lotação é 45 pessoas."
    )



def test_age_range_from_official_source_survives_nli_support(tmp_path: Path) -> None:
    workbench, _, _ = bench(
        tmp_path,
        "O Programa Aprendiz atende jovens de 14 a 24 anos.",
        "A faixa etária do Aprendiz é de 14 a 24 anos.",
        0.95,
    )
    result = workbench.observe("Qual a faixa etária do Programa Aprendiz?")
    assert result.grounding_v3 is not None
    assert result.grounding_v3.reason is V3Reason.SUPPORTED
    assert result.fact_validations[0].status.value == "value_match"



def test_short_age_range_responds_question_without_repeating_attribute(
    tmp_path: Path,
) -> None:
    workbench, _, _ = bench(
        tmp_path,
        "O Senac Aprendiz aceita jovens de 14 a 24 anos.",
        "14 a 24 anos.", 0.96,
    )
    result = workbench.observe("Qual a faixa etária do Senac Aprendiz?")
    assert result.grounding_v3 is not None
    assert result.grounding_v3.reason is V3Reason.SUPPORTED
    assert result.presented_answer == "14 a 24 anos."



def test_catalog_identifies_named_course_even_if_retrieval_misses_it(
    tmp_path: Path,
) -> None:
    retriever = Retriever(
        "Informática Básica tem 80 horas ou 140 horas.",
        entity_id="curso:informatica basica",
    )
    generator = Generator("Excel tem 140 horas.")
    log = ObservationLog(tmp_path / "known-entities.jsonl")
    bench = ObservationWorkbench(
        retriever, generator, NLI(0.99), log,
        mode="enforce",
        adjudicator=EvidenceAdjudicator(
            known_entities=("curso:excel", "curso:informatica basica"),
        ),
    )
    observation = bench.observe("Qual é a carga horária de Excel?")
    assert observation.answerability is not None
    assert observation.answerability.constraints.entity_id == "curso:excel"
    assert observation.answerability.decision.answerable is False
    assert observation.generation_skipped
    assert generator.calls == 0
    assert observation.grounding_v3 is not None
    assert observation.grounding_v3.reason is V3Reason.PRECHECK_BLOCKED
    assert "140 horas" not in observation.presented_answer
