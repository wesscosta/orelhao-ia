import json
from pathlib import Path

import pytest

from orelhao.services.knowledge.answerability_evaluation import (
    evaluate_answerability,
    load_answerability_cases,
)

ROOT = Path(__file__).resolve().parents[2] / "knowledge" / "evaluation"


@pytest.mark.parametrize("dataset", [
    "answerability-stage2-dev.json",
    "answerability-stage2-holdout.json",
])
def test_answerability_synthetic_dataset_is_well_formed(dataset: str) -> None:
    cases = load_answerability_cases(ROOT / dataset)
    assert len(cases) == 60
    assert len({case.case_id for case in cases}) == 60
    assert {case.answerable for case in cases} == {True, False}
    assert len({case.category for case in cases}) == 12
    report = evaluate_answerability(cases)
    assert report["summary"]["cases"] == 60
    assert report["summary"]["tp"] + report["summary"]["tn"] + report["summary"]["fp"] + report["summary"]["fn"] == 60


def test_answerability_dataset_rejects_duplicates(tmp_path: Path) -> None:
    row = {"id": "a", "query": "Teste?", "category": "test", "answerable": False,
           "as_of": "2026-10-29", "evidence": []}
    path = tmp_path / "duplicate.json"
    path.write_text(json.dumps([row, row]))
    with pytest.raises(ValueError, match="duplicado"):
        load_answerability_cases(path)



def test_answerability_cli_smoke(capsys: pytest.CaptureFixture[str]) -> None:
    import argparse

    from orelhao.services.knowledge.cli import _answerability_evaluate

    _answerability_evaluate(argparse.Namespace(
        dataset=ROOT / "answerability-stage2-dev.json",
        as_json=True, diagnostics=False,
    ))
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["cases"] == 60
    assert "results" not in payload
