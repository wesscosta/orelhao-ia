"""Telemetria opt-in de latência, sem áudio, transcrição ou resposta textual.

Distingue início de despacho ao reprodutor de início *audível* (não observado).
O fim real da fala é aproximado pelo último frame positivo do WebRTC VAD.
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
import stat
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

LOG = logging.getLogger(__name__)
MAX_LOG_BYTES = 5_000_000
ALLOWED_METRICS = frozenset({
    "capture_ms", "speech_start_delay_ms", "endpoint_ms", "stt_ms",
    "rag_ms", "tts_ms", "playback_ms", "speech_end_to_dispatch_ms",
    "capture_to_dispatch_ms", "waiting_audio_ms", "input_audio_ms",
    "response_audio_ms", "response_chars",
})


@dataclass(slots=True)
class VoiceLatencyTrace:
    markers: dict[str, int] = field(default_factory=dict)
    speech_started_ns: int | None = None
    last_vad_speech_ns: int | None = None

    def mark(self, name: str) -> None:
        self.markers[name] = time.monotonic_ns()

    def duration(self, start: str, end: str) -> float | None:
        first, last = self.markers.get(start), self.markers.get(end)
        if first is None or last is None or last < first:
            return None
        return (last - first) / 1_000_000

    def metrics(self, *, input_audio_ms: float = 0.0,
                response_audio_ms: float = 0.0, response_chars: int = 0) -> dict[str, float]:
        spans = {
            "capture_ms": ("capture_start", "capture_end"),
            "stt_ms": ("stt_start", "stt_end"),
            "rag_ms": ("rag_start", "rag_end"),
            "tts_ms": ("tts_start", "tts_end"),
            "playback_ms": ("audio_dispatch", "playback_complete"),
            "waiting_audio_ms": ("waiting_audio_start", "waiting_audio_end"),
            "capture_to_dispatch_ms": ("capture_end", "audio_dispatch"),
        }
        result = {key: value for key, (start, end) in spans.items()
                  if (value := self.duration(start, end)) is not None}
        if self.speech_started_ns is not None:
            start = self.markers.get("capture_start")
            if start is not None and self.speech_started_ns >= start:
                result["speech_start_delay_ms"] = (
                    self.speech_started_ns - start
                ) / 1_000_000
        if self.last_vad_speech_ns is not None:
            end = self.markers.get("capture_end")
            dispatch = self.markers.get("audio_dispatch")
            if end is not None and end >= self.last_vad_speech_ns:
                result["endpoint_ms"] = (end - self.last_vad_speech_ns) / 1_000_000
            if dispatch is not None and dispatch >= self.last_vad_speech_ns:
                result["speech_end_to_dispatch_ms"] = (
                    dispatch - self.last_vad_speech_ns
                ) / 1_000_000
        result["input_audio_ms"] = input_audio_ms
        result["response_audio_ms"] = response_audio_ms
        result["response_chars"] = float(response_chars)
        return {k: round(v, 2) for k, v in result.items()
                if k in ALLOWED_METRICS and math.isfinite(v) and v >= 0}


def write_latency_trace(turn: int, route: str, metrics: dict[str, float]) -> bool:
    """Persiste só métricas numéricas, explicitamente habilitadas, após a resposta."""
    if os.environ.get("ORELHAO_LATENCY_ENABLED") != "1":
        return False
    if type(turn) is not int or turn < 1:
        return False
    session = os.environ.get("ORELHAO_MONITOR_SESSION_ID", "")
    if re.fullmatch(r"[a-f0-9]{24}", session) is None:
        return False
    route = route if route in {"guided", "clarification", "rag"} else "other"
    label = os.environ.get("ORELHAO_LATENCY_VARIANT", "baseline")
    if re.fullmatch(r"[a-zA-Z0-9_.-]{1,40}", label) is None:
        label = "baseline"
    selected = {k: round(float(v), 2) for k, v in metrics.items()
                if k in ALLOWED_METRICS and type(v) in (int, float)
                and math.isfinite(float(v)) and v >= 0}
    if not selected:
        return False
    base = Path(os.environ.get(
        "ORELHAO_LATENCY_DIR",
        str(Path.home() / ".local" / "state" / "orelhao-ia" / "latency"),
    ))
    try:
        base.mkdir(mode=0o700, parents=True, exist_ok=True)
        root_stat = base.lstat()
        if not stat.S_ISDIR(root_stat.st_mode) or root_stat.st_uid != os.getuid():
            return False
        base.chmod(0o700)
        target = base / "voice-latency.jsonl"
        payload = json.dumps({
            "at": datetime.now(UTC).isoformat(),
            "session": session,
            "turn": turn,
            "variant": label,
            "route": route,
            "metrics": selected,
        }, separators=(",", ":")).encode("utf-8") + b"\n"
        fd = os.open(
            target,
            os.O_CREAT | os.O_APPEND | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
                return False
            os.fchmod(fd, 0o600)
            if info.st_size + len(payload) > MAX_LOG_BYTES:
                return False
            os.write(fd, payload)
        finally:
            os.close(fd)
    except OSError:
        LOG.debug("Telemetria local de latência não disponível", exc_info=True)
        return False
    return True
