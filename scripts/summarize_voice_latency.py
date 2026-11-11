"""Resumo p50/p90/p95 por variante da telemetria opt-in do Orelhão.

Exemplo: python scripts/summarize_voice_latency.py --path ~/.local/state/orelhao-ia/latency/voice-latency.jsonl
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path


def percentile(samples: list[float], pct: float) -> float:
    values = sorted(samples)
    position = (len(values) - 1) * pct / 100
    lo = int(position)
    hi = min(lo + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (position - lo)


def summarize(path: Path) -> dict[str, dict[str, object]]:
    measurements: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    counts: dict[str, int] = defaultdict(int)
    sessions: dict[str, set[str]] = defaultdict(set)
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict) or not isinstance(obj.get("metrics"), dict):
            continue
        variant = obj.get("variant")
        if not isinstance(variant, str):
            continue
        counts[variant] += 1
        if isinstance(obj.get("session"), str):
            sessions[variant].add(obj["session"])
        for key, value in obj["metrics"].items():
            if (isinstance(key, str) and type(value) in (int, float)
                    and math.isfinite(value) and value >= 0):
                measurements[variant][key].append(float(value))
    summary: dict[str, dict[str, object]] = {}
    for variant in sorted(counts):
        summary[variant] = {
            "turns": counts[variant],
            "distinct_sessions": len(sessions[variant]),
            "minimum_30_turns_met": counts[variant] >= 30,
            "metrics": {
                key: {
                    "n": len(data),
                    "p50": round(percentile(data, 50), 2),
                    "p90": round(percentile(data, 90), 2),
                    "p95": round(percentile(data, 95), 2),
                }
                for key, data in sorted(measurements[variant].items()) if data
            },
        }
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=Path, required=True)
    args = parser.parse_args()
    if not args.path.is_file():
        parser.error("Arquivo não encontrado")
    print(json.dumps(summarize(args.path), ensure_ascii=False, indent=2))
