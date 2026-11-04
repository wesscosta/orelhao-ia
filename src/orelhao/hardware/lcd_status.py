"""LCD 16x2: estados e paginacao opcional de respostas via USB do gancho.

O supervisor e o unico proprietario da porta serial. Texto so aparece se
explicitamente habilitado, permanece em memoria e e limpo ao encerrar a chamada.
"""
from __future__ import annotations

import hashlib
import textwrap
import time
import unicodedata
from typing import Any

VALID_STATES = frozenset({"READY", "LISTENING", "PROCESSING", "SPEAKING", "PAUSED", "ERROR"})
MAX_DISPLAY_CHARS = 480
LCD_COLS = 16

_EVENT_STATE = {
    "session.started": "PROCESSING",
    "voice.greeting": "SPEAKING",
    "voice.listening": "LISTENING",
    "voice.capture": "PROCESSING",
    "voice.transcription": "PROCESSING",
    "voice.transcription_invalid": "LISTENING",
    "voice.context": "PROCESSING",
    "voice.processing": "PROCESSING",
    "voice.waiting": "PROCESSING",
    "voice.paused": "PAUSED",
    "voice.response": "SPEAKING",
    "voice.playback": "SPEAKING",
    "voice.error": "ERROR",
    "voice.idle_timeout": "READY",
}
_RESPONSE_BOUNDARIES = frozenset({
    "session.started", "session.ended", "voice.greeting", "voice.listening",
    "voice.capture", "voice.transcription", "voice.transcription_invalid",
    "voice.context", "voice.processing", "voice.waiting", "voice.paused",
    "voice.error", "voice.idle_timeout",
})


def choose_state(snapshot: dict[str, Any], session_id: str | None) -> str:
    """Nao misturar estados entre sessoes."""
    if not session_id:
        return "READY"
    if not snapshot.get("active") or snapshot.get("session_id") != session_id:
        return "PROCESSING"
    events = snapshot.get("events", [])
    if not isinstance(events, list):
        return "PROCESSING"
    for event in reversed(events):
        if isinstance(event, dict):
            kind = event.get("type")
            status = _EVENT_STATE.get(kind) if isinstance(kind, str) else None
            if status is not None:
                return status
    return "PROCESSING"


def latest_answer(snapshot: dict[str, Any], session_id: str) -> tuple[str, str] | None:
    """Retorna somente a ultima resposta ainda relevante para o turno atual."""
    if not snapshot.get("active") or snapshot.get("session_id") != session_id:
        return None
    events = snapshot.get("events", [])
    if not isinstance(events, list):
        return None
    for event in reversed(events):
        if not isinstance(event, dict):
            continue
        kind = event.get("type")
        if kind in _RESPONSE_BOUNDARIES:
            return None
        if kind == "voice.playback" and event.get("status") == "despedida":
            return None
        if kind == "voice.response":
            value = event.get("text")
            if isinstance(value, str) and value.strip():
                # Digest nao divulga conteudo. Timestamp/turno evita reusar pagina antiga.
                digest = hashlib.blake2s(value.encode("utf-8"), digest_size=8).hexdigest()
                token = f"{session_id}:{event.get('turn')}:{event.get('timestamp')}:{digest}"
                return token, value
            return None
    return None


def display_pages(text: str, *, max_chars: int = MAX_DISPLAY_CHARS) -> list[tuple[str, str]]:
    """Normaliza portugues para ASCII HD44780 e empacota duas linhas por pagina."""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(
        char for char in normalized
        if not unicodedata.combining(char) and (char.isspace() or 32 <= ord(char) <= 126)
    )
    clean = " ".join(ascii_text.replace("|", "/").split())
    if not clean:
        return []
    if len(clean) > max_chars:
        clean = clean[:max_chars - 3].rstrip() + "..."
    lines = textwrap.wrap(
        "LUMI: " + clean, width=LCD_COLS, break_long_words=True,
        break_on_hyphens=False,
    )
    return [
        (lines[i], lines[i + 1] if i + 1 < len(lines) else "")
        for i in range(0, len(lines), 2)
    ]


class LCDStatusBridge:
    """Deduplica comandos, pagina respostas e nao bloqueia a leitura do gancho."""

    def __init__(
        self, interval: float = 0.7, *, show_answers: bool = False,
        page_seconds: float = 2.3,
    ) -> None:
        self.interval = interval
        self.show_answers = show_answers
        self.page_seconds = page_seconds
        self.last_state: str | None = None
        self.next_poll = 0.0
        self._token: str | None = None
        self._pages: list[tuple[str, str]] = []
        self._page_index = -1
        self._next_page = 0.0

    def _forget_text(self) -> None:
        self._token = None
        self._pages.clear()
        self._page_index = -1
        self._next_page = 0.0

    def reset(self) -> None:
        self._forget_text()
        self.last_state = None
        self.next_poll = 0.0

    def send(self, port: Any, state: str) -> None:
        if state not in VALID_STATES or state == self.last_state:
            return
        port.write(f"LCD:STATE:{state}\n".encode("ascii"))
        self.last_state = state

    def _send_text(self, port: Any, token: str, text: str, now: float) -> bool:
        if token != self._token:
            self._forget_text()
            self._token = token
            self._pages = display_pages(text)
            self._next_page = now
        if not self._pages:
            return False
        if now >= self._next_page:
            self._page_index = (self._page_index + 1) % len(self._pages)
            line1, line2 = self._pages[self._page_index]
            port.write(f"LCD:TEXT:{line1}|{line2}\n".encode("ascii"))
            self._next_page = now + self.page_seconds
            self.last_state = None  # Proximo estado sempre sobrescreve a ultima pagina.
        return True

    def tick(
        self, port: Any, *, session_id: str | None,
        snapshot_fn: Any, now: float | None = None,
    ) -> None:
        instant = time.monotonic() if now is None else now
        if instant < self.next_poll:
            return
        self.next_poll = instant + self.interval
        if session_id is None:
            self._forget_text()
            self.send(port, "READY")
            return
        current = snapshot_fn()
        if self.show_answers:
            response = latest_answer(current, session_id)
            if response is not None and self._send_text(port, *response, now=instant):
                return
        self._forget_text()
        self.send(port, choose_state(current, session_id))
