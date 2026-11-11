"""Benchmark reprodutível do TTS local (sem microfone/LLM nem rede)."""
from __future__ import annotations

import argparse
import json
import platform
import resource
import statistics
import time
from pathlib import Path

from orelhao.config import TTSConfig
from orelhao.services.tts.service import PiperTTSService

PHRASES = (
    "Olá! Eu sou o Lumi. Como posso ajudar?",
    "Quais cursos de informática o Senac Piauí oferece?",
    "A unidade Senac Centro fica em Teresina.",
    "Para informações atualizadas sobre matrícula, consulte o atendimento.",
    "Posso ajudar com cursos, unidades e serviços do Senac Piauí.",
    "O Senac comemora oitenta anos em dois mil e vinte e seis.",
)


def percentile(values: list[float], percentage: int) -> float:
    values = sorted(values)
    rank = (len(values) - 1) * percentage / 100
    lower = int(rank)
    fraction = rank - lower
    return values[lower] + fraction * (values[min(lower + 1, len(values) - 1)] - values[lower])


def run(args: argparse.Namespace) -> dict[str, object]:
    config = TTSConfig(
        executable=args.executable,
        model=args.model,
        config=args.model_config,
        length_scale=args.length_scale,
    )
    usage_kind = resource.RUSAGE_CHILDREN if args.engine == "cli" else resource.RUSAGE_SELF
    usage_before = resource.getrusage(usage_kind)
    service = PiperTTSService(config)
    if args.engine == "resident":
        from orelhao.services.tts.resident import PiperResidentTTSService
        service = PiperResidentTTSService(config)
    init_start = time.monotonic()
    if args.engine == "resident":
        service.prepare()
    preparation_ms = (time.monotonic() - init_start) * 1000
    # Aquecimento fora da amostra, igual para os dois caminhos.
    service.synthesize(PHRASES[0])
    elapsed: list[float] = []
    durations: list[float] = []
    for idx in range(args.samples):
        phrase = PHRASES[idx % len(PHRASES)]
        started = time.monotonic()
        audio = service.synthesize(phrase)
        elapsed.append((time.monotonic() - started) * 1000)
        durations.append(audio.duration_seconds)
        if (idx + 1) % 5 == 0:
            print(f"{args.engine}: {idx + 1}/{args.samples}", flush=True)
    usage_after = resource.getrusage(usage_kind)
    results: dict[str, object] = {
        "process_group_measured": "piper_children" if args.engine == "cli" else "python_parent",
        "cpu_user_seconds": round(usage_after.ru_utime - usage_before.ru_utime, 3),
        "cpu_system_seconds": round(usage_after.ru_stime - usage_before.ru_stime, 3),
        "peak_rss_kib": usage_after.ru_maxrss,
        "engine": args.engine,
        "samples": args.samples,
        "model": Path(args.model).name,
        "python": platform.python_version(),
        "host_os": platform.system(),
        "notes": "TTS isolado no notebook, não mede resposta fim-da-fala até alto-falante",
        "preparation_ms": round(preparation_ms, 2),
        "warmup_excluded": True,
        "p50_ms": round(percentile(elapsed, 50), 2),
        "p90_ms": round(percentile(elapsed, 90), 2),
        "p95_ms": round(percentile(elapsed, 95), 2),
        "mean_ms": round(statistics.mean(elapsed), 2),
        "min_ms": round(min(elapsed), 2),
        "max_ms": round(max(elapsed), 2),
        "audio_duration_seconds_range": [round(min(durations), 2), round(max(durations), 2)],
        "samples_ms": [round(value, 2) for value in elapsed],
    }
    print(json.dumps(results, indent=2, ensure_ascii=False), flush=True)
    if args.output:
        dest = Path(args.output)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", choices=("cli", "resident"), required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-config", required=True)
    parser.add_argument("--executable", default="piper")
    parser.add_argument("--length-scale", type=float, default=0.88)
    parser.add_argument("--samples", type=int, default=30)
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.samples < 1:
        parser.error("--samples deve ser positivo")
    run(args)
