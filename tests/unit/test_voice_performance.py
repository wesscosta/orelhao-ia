"""Métricas monotônicas são numéricas e não armazenam áudio ou texto."""
from __future__ import annotations

import json
import stat

from orelhao.hardware.performance import VoiceLatencyTrace, write_latency_trace


def test_latency_trace_separates_endpoint_from_processing():
    trace = VoiceLatencyTrace(
        markers={
            "capture_start": 1_000_000_000, "capture_end": 3_000_000_000,
            "stt_start": 3_100_000_000, "stt_end": 3_500_000_000,
            "rag_start": 3_500_000_000, "rag_end": 4_300_000_000,
            "tts_start": 4_300_000_000, "tts_end": 4_500_000_000,
            "audio_dispatch": 4_510_000_000, "playback_complete": 6_510_000_000,
        },
        speech_started_ns=1_300_000_000,
        last_vad_speech_ns=2_300_000_000,
    )
    result = trace.metrics(
        input_audio_ms=1700, response_audio_ms=2000, response_chars=55
    )
    assert result["speech_start_delay_ms"] == 300
    assert result["endpoint_ms"] == 700
    assert result["speech_end_to_dispatch_ms"] == 2210
    assert result["capture_to_dispatch_ms"] == 1510
    assert result["stt_ms"] == 400
    assert result["rag_ms"] == 800
    assert result["tts_ms"] == 200
    assert result["playback_ms"] == 2000
    assert result["response_audio_ms"] == 2000


def test_latency_logging_is_opt_in_and_numeric_only(tmp_path, monkeypatch):
    monkeypatch.setenv("ORELHAO_LATENCY_DIR", str(tmp_path))
    monkeypatch.setenv("ORELHAO_MONITOR_SESSION_ID", "a" * 24)
    monkeypatch.delenv("ORELHAO_LATENCY_ENABLED", raising=False)
    assert not write_latency_trace(1, "rag", {"tts_ms": 100})
    assert list(tmp_path.iterdir()) == []
    monkeypatch.setenv("ORELHAO_LATENCY_ENABLED", "1")
    assert write_latency_trace(
        1, "rag", {"tts_ms": 100.4, "not_allowed": 1, "response_chars": 27}
    )
    target = tmp_path / "voice-latency.jsonl"
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert stat.S_IMODE(tmp_path.stat().st_mode) == 0o700
    record = json.loads(target.read_text())
    assert record["session"] == "a" * 24
    assert record["metrics"] == {"tts_ms": 100.4, "response_chars": 27}
    assert not any(k in record for k in ("question", "text", "transcription", "audio"))


def test_latency_logging_rejects_invalid_session_and_invalid_numbers(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("ORELHAO_LATENCY_DIR", str(tmp_path))
    monkeypatch.setenv("ORELHAO_LATENCY_ENABLED", "1")
    monkeypatch.setenv("ORELHAO_MONITOR_SESSION_ID", "../invalid")
    assert not write_latency_trace(1, "rag", {"tts_ms": 25})
    monkeypatch.setenv("ORELHAO_MONITOR_SESSION_ID", "f" * 24)
    assert not write_latency_trace(1, "rag", {"tts_ms": float("nan")})
