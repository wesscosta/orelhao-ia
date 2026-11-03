"""Benchmark serial e reproduzível de LLMs locais, sem trocar o modelo ativo."""
from __future__ import annotations

import json
import math
import platform
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from time import perf_counter
from typing import Any

from orelhao.services.llm.service import INSUFFICIENT_CONTEXT, LocalOpenAICompatibleLLMService
from orelhao.services.rag.retriever import RetrievedContext


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    case_id: str
    question: str
    context: tuple[RetrievedContext, ...]
    expected_abstain: bool | None = None
    must_include: tuple[str, ...] = ()
    must_not_include: tuple[str, ...] = ()


def _phrases(record: dict[str, Any], key: str) -> tuple[str, ...]:
    values = record.get(key, [])
    if not isinstance(values, list) or any(not isinstance(x, str) or not x for x in values):
        raise TypeError(f"{key} deve ser lista de textos")
    return tuple(values)


def load_cases(path: Path) -> list[BenchmarkCase]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or not isinstance(doc.get("cases"), list):
        raise TypeError("Dataset precisa conter lista 'cases'")
    cases: list[BenchmarkCase] = []
    ids: set[str] = set()
    for raw in doc["cases"]:
        if not isinstance(raw, dict):
            raise TypeError("Caso deve ser um objeto")
        ident = raw.get("id")
        question = raw.get("question")
        context = raw.get("evidence")
        expected = raw.get("expected_abstain")
        if not isinstance(ident, str) or not ident or ident in ids:
            raise ValueError("IDs de casos devem ser únicos e não vazios")
        if not isinstance(question, str) or not question.strip():
            raise ValueError("Pergunta vazia ou inválida")
        if not isinstance(context, list):
            raise TypeError("evidence deve ser lista")
        if expected is not None and not isinstance(expected, bool):
            raise ValueError("expected_abstain deve ser booleano")
        items: list[RetrievedContext] = []
        for item in context:
            if not isinstance(item, dict) or not isinstance(item.get("source"), str) or not isinstance(item.get("text"), str):
                raise TypeError("evidence exige source e text")
            items.append(RetrievedContext(text=item["text"], source=item["source"]))
        required = _phrases(raw, "must_include")
        forbidden = _phrases(raw, "must_not_include")
        cases.append(BenchmarkCase(ident, question, tuple(items), expected, required, forbidden))
        ids.add(ident)
    if not cases:
        raise ValueError("Dataset sem casos")
    return cases


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)]


def _rss_kib(pid: int | None) -> int | None:
    if pid is None:
        return None
    try:
        lines = Path(f"/proc/{pid}/status").read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        if line.startswith("VmRSS:"):
            return int(line.split()[1])
    return None


def evaluate(
    service: LocalOpenAICompatibleLLMService,
    cases: list[BenchmarkCase],
    *,
    server_pid: int | None = None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for case in cases:
        start = perf_counter()
        try:
            completion = service.generate_completion(case.question, list(case.context))
            result = completion.text.strip()
            elapsed_ms = (perf_counter() - start) * 1000.0
            abstained = result == INSUFFICIENT_CONTEXT
            checks: list[bool] = []
            if case.expected_abstain is not None:
                checks.append(abstained == case.expected_abstain)
            if not abstained:
                folded = result.casefold()
                checks.extend(phrase.casefold() in folded for phrase in case.must_include)
                checks.extend(phrase.casefold() not in folded for phrase in case.must_not_include)
            elif case.must_include:
                checks.append(False)
            passed = all(checks) if checks else None
            rows.append({
                "id": case.case_id, "response": result, "raw_response": completion.raw_text,
                "abstained": abstained,
                "passed_mechanical_checks": passed, "latency_ms": round(elapsed_ms, 2),
                "prompt_tokens": completion.prompt_tokens,
                "completion_tokens": completion.completion_tokens,
                "generation_tokens_per_second": completion.tokens_per_second,
                "server_rss_kib": _rss_kib(server_pid), "error": None,
            })
        except (RuntimeError, ValueError, OSError) as exc:
            rows.append({
                "id": case.case_id, "response": None, "raw_response": None,
                "abstained": None,
                "passed_mechanical_checks": False,
                "latency_ms": round((perf_counter() - start) * 1000.0, 2),
                "prompt_tokens": None, "completion_tokens": None,
                "generation_tokens_per_second": None, "server_rss_kib": _rss_kib(server_pid),
                "error": str(exc)[:300],
            })
    durations = [row["latency_ms"] for row in rows if row["error"] is None]
    checked = [row["passed_mechanical_checks"] for row in rows if row["passed_mechanical_checks"] is not None]
    return {
        "schema_version": 1,
        "model": service.config.model,
        "configuration": {
            "temperature": service.config.temperature,
            "max_tokens": service.config.max_tokens,
            "max_context_chars": service.config.max_context_chars,
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "summary": {
            "cases": len(rows), "completed": len(durations), "errors": len(rows) - len(durations),
            "p50_ms": median(durations) if durations else None,
            "p95_ms": _percentile(durations, 0.95) if durations else None,
            "mechanical_pass_rate": sum(checked) / len(checked) if checked else None,
            "quality_human_reviewed": False,
        },
        "results": rows,
    }
