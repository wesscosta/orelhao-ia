"""CLI de benchmark isolado, executa um modelo previamente carregado no servidor local."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from orelhao.config import load_config
from orelhao.runtime_paths import resolve_project_path

from .benchmark import evaluate, load_cases
from .service import LocalOpenAICompatibleLLMService


def add_llm_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("llm-benchmark", help="avalia LLM local em casos versionados")
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--model", help="alias do modelo já servido em localhost")
    parser.add_argument("--base-url", help="URL da API local (loopback), por exemplo http://127.0.0.1:8081/v1")
    parser.add_argument("--max-tokens", type=int, default=96)
    parser.add_argument("--max-context-chars", type=int, default=1800)
    parser.add_argument("--server-pid", type=int, help="PID opcional do servidor no Linux")
    parser.add_argument("--output", type=Path, required=True)
    parser.set_defaults(handler=_run)


def _run(args: argparse.Namespace) -> None:
    config_path = os.getenv("ORELHAO_CONFIG", "config/development.yaml")
    config = load_config(resolve_project_path(config_path)).llm
    config = config.model_copy(update={
        "model": args.model or config.model,
        "base_url": args.base_url or config.base_url,
        "max_tokens": args.max_tokens,
        "max_context_chars": args.max_context_chars,
    })
    cases = load_cases(args.dataset)
    service = LocalOpenAICompatibleLLMService(config)
    health = service.health()
    if not health.available:
        raise SystemExit(f"LLM indisponível: {health.detail}")
    report = evaluate(service, cases, server_pid=args.server_pid)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
