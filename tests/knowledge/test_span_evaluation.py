from pathlib import Path

from orelhao.services.knowledge.evidence import NliProbabilities
from orelhao.services.knowledge.live_pipeline_evaluation import LiveCase
from orelhao.services.knowledge.models import Chunk
from orelhao.services.knowledge.span_evaluation import (
    compare_nli_spans,
    diagnose_expected_source_misses,
)


def test_retrospective_retrieval_miss_does_not_affect_runtime() -> None:
    cases = [LiveCase("P13", "Idade do curso?", False, "course", ("14",), "course.md")]
    results = {
        "tucano2": [{"id": "P13", "evidence_sources": ["other.md"]}],
    }
    report = diagnose_expected_source_misses(
        cases, results, indexed_chunks=[
            Chunk("course:0", "course", "Idade: 14 anos.", "course.md", 0)
        ],
    )
    assert report["count"] == 1
    assert report["expected_source_indexed"] == 1
    assert report["cases"][0]["retrieval_miss"]


def test_span_nli_compare_uses_two_premises_with_same_claim(monkeypatch, tmp_path: Path) -> None:
    import orelhao.services.knowledge.span_evaluation as module

    item = Chunk(
        "x:0", "x", "Conteúdo irrelevante.\nO prazo é de 15 dias úteis.", "x.md", 0,
    )
    calls: list[tuple[str, str]] = []

    class FakeNLI:
        def __init__(self, model_path: Path) -> None:
            assert model_path == tmp_path

        def classify(self, query: str, passage: str) -> NliProbabilities:
            calls.append((query, passage))
            if "\n" in passage:
                return NliProbabilities(.4, .5, .1)
            return NliProbabilities(.8, .1, .1)

    monkeypatch.setattr(module, "OnnxNliEvidenceVerifier", FakeNLI)
    monkeypatch.setattr(module, "load_chunks", lambda index_dir: [item])
    result = compare_nli_spans(
        {"demo": [{"id": "P08", "claim_assessments": [{
            "claim": "O prazo é de 15 dias úteis.", "chunk_id": "x:0", "score": .4,
        }]}]},
        model_path=tmp_path, index_dir=tmp_path,
    )
    assert len(calls) == 2
    assert calls[0][0] == calls[1][0]
    assert result["paired_nli_observations"] == 1
    assert result["span_score_higher"] == 1
    details = result["cases"][0]
    assert details["delta_entailment"] == .4
    assert details["span"]["span"]["start"] == item.text.index("O prazo")
    assert details["span"]["support_verified"] is False


def test_unsupported_claim_without_lexical_overlap_not_guessed(monkeypatch, tmp_path: Path) -> None:
    import orelhao.services.knowledge.span_evaluation as module

    item = Chunk("id", "doc", "A biblioteca funciona.", "library.md", 0)
    class FakeNLI:
        def __init__(self, model_path: Path) -> None:
            pass
        def classify(self, query: str, passage: str) -> NliProbabilities:
            raise AssertionError("NLI não deve ser chamada sem span lexical")

    monkeypatch.setattr(module, "OnnxNliEvidenceVerifier", FakeNLI)
    monkeypatch.setattr(module, "load_chunks", lambda index_dir: [item])
    result = compare_nli_spans(
        {"demo": [{"id": "test", "claim_assessments": [{
            "chunk_id": "id", "claim": "O prazo do edital encerra amanhã."
        }]}]},
        model_path=tmp_path, index_dir=tmp_path,
    )
    assert result["no_lexical_span"] == 1
    assert result["paired_nli_observations"] == 0
