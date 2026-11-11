"""Script de percentis não confunde falta de 30 turnos com evidência."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_latency_summary_reports_counts_and_percentiles(tmp_path: Path) -> None:
    log = tmp_path / "voice-latency.jsonl"
    with log.open("w", encoding="utf-8") as file:
        for index in range(30):
            file.write(json.dumps({
                "session": "f" * 24,
                "variant": "resident",
                "metrics": {"tts_ms": float(index + 1)},
            }) + "\n")
        file.write(json.dumps({
            "session": "a" * 24,
            "variant": "baseline",
            "metrics": {"tts_ms": 300.0},
        }) + "\n")
    script = Path(__file__).resolve().parents[2] / "scripts" / "summarize_voice_latency.py"
    result = subprocess.run(
        [sys.executable, str(script), "--path", str(log)],
        capture_output=True, text=True, check=True,
    )
    report = json.loads(result.stdout)
    assert report["resident"]["turns"] == 30
    assert report["resident"]["minimum_30_turns_met"]
    assert report["resident"]["metrics"]["tts_ms"]["p50"] == 15.5
    assert report["baseline"]["turns"] == 1
    assert not report["baseline"]["minimum_30_turns_met"]
