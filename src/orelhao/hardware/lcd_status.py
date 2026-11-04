"""Emissor opcional de estado para LCD I2C no mesmo USB do gancho.

Nao transmite perguntas ou respostas; apenas estados enum. Sem segunda
abertura da porta serial, sem dependencia do LCD para manter voz ativa.
"""
from __future__ import annotations

import time
from typing import Any

VALID_STATES = frozenset({"READY", "LISTENING", "PROCESSING", "SPEAKING", "PAUSED", "ERROR"})
_EVENT_STATE = {
    "session.started": "PROCESSING",
    "voice.greeting": "SPEAKING",
    "voice.listening": "LISTENING",
    "voice.capture": "PROCESSING",
    "voice.transcription": "PROCESSING",
    "voice.transcription_invalid": "LISTENING",
    "voice.context": "PROCESSING",
    "voice.processing": "PROCESSING",
    "voice.waiting": "PAUSED",
    "voice.paused": "PAUSED",
    "voice.response": "SPEAKING",
    "voice.playback": "SPEAKING",
    "voice.error": "ERROR",
    "voice.idle_timeout": "READY",
}


def choose_state(snapshot: dict[str, Any], session_id: str | None) -> str:
    """Estado sem texto do usuario e sem inferir a partir de eventos antigos."""
    if not session_id:
        return "READY"
    if not snapshot.get("active") or snapshot.get("session_id") != session_id:
        return "PROCESSING"
    events = snapshot.get("events", [])
    if not isinstance(events, list) or not events:
        return "PROCESSING"
    for event in reversed(events):
        if isinstance(event, dict):
            status = _EVENT_STATE.get(event.get("type"))
            if status is not None:
                return status
    return "PROCESSING"


class LCDStatusBridge:
    """Deduplica os comandos e limita leitura de telemetria temporaria."""

    def __init__(self, interval: float = 0.7) -> None:
        self.interval = interval
        self.last_state: str | None = None
        self.next_poll = 0.0

    def reset(self) -> None:
        self.last_state = None
        self.next_poll = 0.0

    def send(self, port: Any, state: str) -> None:
        if state not in VALID_STATES or state == self.last_state:
            return
        port.write(f"LCD:STATE:{state}\n".encode("ascii"))
        self.last_state = state

    def tick(self, port: Any, *, session_id: str | None,
             snapshot_fn: Any, now: float | None = None) -> None:
        instant = time.monotonic() if now is None else now
        if instant < self.next_poll:
            return
        self.next_poll = instant + self.interval
        if session_id is None:
            self.send(port, "READY")
        else:
            self.send(port, choose_state(snapshot_fn(), session_id))
