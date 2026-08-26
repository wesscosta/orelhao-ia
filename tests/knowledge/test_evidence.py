from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from orelhao.services.knowledge.evidence import (
    EvidenceFilteredRetriever,
    evidence_model_directory,
    evidence_model_filename,
    provision_evidence_model,
)
from orelhao.services.knowledge.models import Chunk, SearchResult


def _result(chunk_id: str, text: str) -> SearchResult:
    return SearchResult(
        chunk=Chunk(chunk_id, chunk_id, text, f"{chunk_id}.md", 0),
        score=0.8,
    )


@dataclass
class StaticRetriever:
    results: list[SearchResult]

    def search(self, query: str, *, limit: int = 4) -> list[SearchResult]:
        return self.results[:limit]


@dataclass
class StaticVerifier:
    scores: dict[str, float]

    def support_score(self, query: str, passage: str) -> float:
        del query
        return self.scores[passage]


def test_evidence_filter_preserves_order_and_removes_unsupported_chunks() -> None:
    supported = _result("supported", "resposta presente")
    unsupported = _result("unsupported", "assunto relacionado")
    retriever = EvidenceFilteredRetriever(
        StaticRetriever([unsupported, supported]),
        StaticVerifier({"resposta presente": 0.9, "assunto relacionado": 0.2}),
        min_support=0.5,
    )

    results = retriever.search("pergunta")
    assert [result.chunk.id for result in results] == [supported.chunk.id]
    assert results[0].score == supported.score
    assert results[0].chunk.metadata["evidence_support"] == "0.900000"


def test_evidence_filter_abstains_when_no_chunk_is_supported() -> None:
    candidate = _result("candidate", "sem resposta")
    retriever = EvidenceFilteredRetriever(
        StaticRetriever([candidate]),
        StaticVerifier({"sem resposta": 0.4}),
        min_support=0.5,
    )

    assert retriever.search("pergunta") == []


@pytest.mark.parametrize("min_support", [-0.1, 1.1])
def test_evidence_filter_rejects_invalid_threshold(min_support: float) -> None:
    with pytest.raises(ValueError, match="min_support"):
        EvidenceFilteredRetriever(StaticRetriever([]), StaticVerifier({}), min_support=min_support)


def test_evidence_model_variants_have_distinct_local_files() -> None:
    assert evidence_model_filename("int8") == "model_int8.onnx"
    assert evidence_model_filename("fp32") == "model_fp32.onnx"


def test_evidence_model_rejects_unknown_variant() -> None:
    with pytest.raises(ValueError, match="variant"):
        evidence_model_filename("unknown")


def test_mdeberta_candidate_supports_only_int8() -> None:
    assert evidence_model_directory("mdeberta-v3") == "mdeberta-v3-base-squad2"
    assert evidence_model_filename("int8", model="mdeberta-v3") == "model_int8.onnx"
    with pytest.raises(ValueError, match="variant"):
        evidence_model_filename("fp32", model="mdeberta-v3")


def test_provision_evidence_model_keeps_variants_side_by_side(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    (downloads / "model.onnx").write_bytes(b"fp32")
    (downloads / "tokenizer.json").write_text("{}", encoding="utf-8")

    def fake_download(*, filename: str, **_: str) -> str:
        return str(downloads / Path(filename).name)

    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub",
        SimpleNamespace(hf_hub_download=fake_download),
    )
    model_dir = tmp_path / "model"

    manifest = provision_evidence_model(model_dir, model="xlm-roberta", variant="fp32")

    assert (model_dir / "model_fp32.onnx").read_bytes() == b"fp32"
    assert not (model_dir / "model_int8.onnx").exists()
    assert manifest["variant"] == "fp32"
    stored = json.loads((model_dir / "manifest-fp32.json").read_text(encoding="utf-8"))
    assert stored["model_file"] == "model_fp32.onnx"
