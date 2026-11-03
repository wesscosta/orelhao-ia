"""Executa avaliação textual real, offline e reproduzível, sem testar STT/TTS.

Exemplo:
.venv/bin/python scripts/run_live_grounding_gate.py
  --config config/benchmark-tucano2-15b-ptbr.yaml
  --dataset knowledge/evaluation/grounding-real-senac-pi-v1.json
  --output /tmp/orelhao-grounding-real-ptbr.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from orelhao.config import load_config
from orelhao.services.knowledge.live_pipeline_evaluation import (
    assess_live_case,
    load_live_cases,
    summarize_live_cases,
)
from orelhao.services.knowledge.observation import (
    LocalLLMAnswerGenerator,
    build_default_observation_workbench,
)
from orelhao.services.knowledge.paths import default_knowledge_paths
from orelhao.services.llm.service import LocalOpenAICompatibleLLMService


def main() -> int:
    parser = argparse.ArgumentParser(description="Avaliação adversarial real do pipeline textual")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("observe", "enforce"), default="enforce")
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--case-id", action="append", default=[], help="ID a executar (repetível)")
    args = parser.parse_args()
    config = load_config(args.config)
    as_of, cases = load_live_cases(args.dataset)
    if args.max_cases < 0:
        raise ValueError("max-cases não pode ser negativo")
    if args.case_id:
        selected = set(args.case_id)
        cases = [case for case in cases if case.case_id in selected]
        missing = selected - {case.case_id for case in cases}
        if missing:
            raise ValueError(f"case-id inexistente: {sorted(missing)}")
    if args.max_cases:
        cases = cases[:args.max_cases]
    paths = default_knowledge_paths()
    workbench = build_default_observation_workbench(
        paths.index,
        log_path=Path("/tmp/orelhao-live-gate-observations.jsonl"),
        answer_generator=LocalLLMAnswerGenerator(
            LocalOpenAICompatibleLLMService(config.llm)
        ),
    )
    results: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for i, case in enumerate(cases, 1):
        try:
            obs = workbench.observe(case.query, mode=args.mode, limit=8)
            data = assess_live_case(case, obs)
            results.append(data)
            ok = not data["false_allow"] and not data["false_block"] and (
                case.expected_abstain or data["text_anchor_pass"] is True
            )
            status = "OK" if ok else "REVISAR"
            print(
                f"{i:02d}/{len(cases)} {case.case_id}: {status}"
                f" pre={data['answerability_reason'] or '-'}"
                f" grounding={data['grounding_status']}"
                f" abstain={data['predicted_abstain']}"
                f" latency={obs.latency.total_ms:.1f}ms",
                flush=True,
            )
        except (RuntimeError, ValueError, TimeoutError, OSError) as exc:
            failures.append({"id": case.case_id, "error": str(exc)})
            print(f"{i:02d}/{len(cases)} {case.case_id}: ERRO {exc}", flush=True)
        payload = {
            "meta": {
                "created_at": datetime.now(UTC).isoformat(),
                "dataset": str(args.dataset),
                "as_of": as_of,
                "model": config.llm.model,
                "base_url": config.llm.base_url,
                "mode": args.mode,
                "evaluation_status": "provisional; requires independent human adjudication",
                "completed": i == len(cases),
                "total_cases": len(cases),
            },
            "summary": {
                **summarize_live_cases(results),
                "execution_errors": len(failures),
                "not_completed": len(cases) - i,
            },
            "results": results,
            "errors": failures,
        }
        temp = args.output.with_suffix(".tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp.replace(args.output)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
