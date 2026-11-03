from __future__ import annotations

import json
from pathlib import Path

import pytest

from orelhao.config import LLMConfig
from orelhao.services.llm.benchmark import BenchmarkCase, evaluate, load_cases
from orelhao.services.llm.service import INSUFFICIENT_CONTEXT, LLMCompletion
from orelhao.services.rag.retriever import RetrievedContext


class FakeService:
    config = LLMConfig(model="mock")

    def generate_completion(self, query: str, context: list[RetrievedContext]) -> LLMCompletion:
        if not context:
            return LLMCompletion(INSUFFICIENT_CONTEXT)
        return LLMCompletion("O atendimento ocorre de segunda a sexta.", completion_tokens=11)


def test_dataset_validates_shape(tmp_path: Path) -> None:
    file = tmp_path / "cases.json"
    file.write_text(json.dumps({"cases": [
        {"id": "a", "question": "Horário?", "evidence": [{"text": "abc", "source": "f"}]}
    ]}))
    assert load_cases(file)[0].case_id == "a"
    with pytest.raises(ValueError, match="únicos"):
        file.write_text(json.dumps({"cases": [
            {"id": "a", "question": "X", "evidence": []},
            {"id": "a", "question": "Y", "evidence": []},
        ]}))
        load_cases(file)


def test_benchmark_reports_abstention_and_latency() -> None:
    cases = [
        BenchmarkCase("one", "quando?", (RetrievedContext("Abertura", "faq"),), False, ("segunda",)),
        BenchmarkCase("two", "quanto?", (), True),
    ]
    report = evaluate(FakeService(), cases)  # type: ignore[arg-type]
    assert report["summary"]["completed"] == 2
    assert report["summary"]["mechanical_pass_rate"] == 1.0
    assert report["summary"]["quality_human_reviewed"] is False
    assert report["results"][1]["abstained"] is True
    assert report["results"][0]["completion_tokens"] == 11
