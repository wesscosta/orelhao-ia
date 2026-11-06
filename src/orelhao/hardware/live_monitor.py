"""Observabilidade efêmera da chamada física, sem duplicar STT/LLM/TTS.

Comunicação entre processos por eventos JSONL pequenos em tmpfs (XDG_RUNTIME_DIR).
O arquivo é substituído no início e no fim de cada ligação. Ao encerrar, o
conteúdo textual é eliminado; nenhum áudio bruto é registrado neste canal.
A falha do monitor jamais pode interromper o atendimento.
"""
from __future__ import annotations

import json
import logging
import os
import secrets
import stat
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LOG = logging.getLogger(__name__)
FILE_NAME = "live-session.jsonl"
MAX_FILE_BYTES = 131_072
MAX_EVENTS = 100
MAX_TEXT = 1800
ALLOWED_TYPES = frozenset({
    "session.started", "session.ended", "voice.greeting",
    "voice.listening", "voice.capture", "voice.transcription",
    "voice.transcription_invalid", "voice.context", "voice.processing", "voice.waiting",
    "voice.paused", "voice.idle_timeout",
    "voice.response", "voice.playback", "voice.error",
})


def _file() -> Path | None:
    base = os.environ.get("ORELHAO_MONITOR_DIR")
    if base is None:
        base = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
        if not Path(base).is_dir():
            return None
        root = Path(base) / "orelhao-ia"
    else:
        root = Path(base)
    try:
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = root.stat()
        if info.st_uid != os.getuid() or not stat.S_ISDIR(info.st_mode):
            return None
        root.chmod(0o700)
    except OSError:
        return None
    return root / FILE_NAME


def _event(session_id: str, kind: str, **details: Any) -> dict[str, Any]:
    event: dict[str, Any] = {
        "session_id": session_id,
        "type": kind,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    for key, value in details.items():
        if key not in {"turn", "text", "status", "reason", "route", "metrics"}:
            continue
        if isinstance(value, str):
            event[key] = value[:MAX_TEXT]
        elif key == "turn" and type(value) is int:
            event[key] = value
        elif key == "metrics" and isinstance(value, dict):
            event[key] = {
                k: round(float(v), 2)
                for k, v in value.items()
                if isinstance(k, str) and len(k) < 45
                and type(v) in (float, int)
            }
    return event


def _replace(path: Path, event: dict[str, Any]) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".session-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def voice_observation_log_path() -> Path | None:
    """Log de grounding da chamada no tmpfs, removido ao desligar o monofone."""
    session = os.environ.get("ORELHAO_MONITOR_SESSION_ID", "")
    if len(session) != 24 or any(c not in "0123456789abcdef" for c in session):
        return None
    view = _file()
    return view.parent / f"grounding-{session}.jsonl" if view is not None else None


def start_session() -> str:
    """O supervisor inicia uma única sessão; reinicia a view sem histórico antigo."""
    session_id = secrets.token_hex(12)
    path = _file()
    if path is not None:
        try:
            _replace(path, _event(session_id, "session.started", status="iniciando"))
        except OSError as exc:
            LOG.warning("Monitor não disponível: %s", exc)
    from orelhao.hardware.audio_diagnostics import authorize_started_session
    from orelhao.hardware.audit import record_event
    record_event(session_id, "session.started", status="iniciando")
    authorize_started_session(session_id)
    return session_id


def _existing_session(path: Path) -> str | None:
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "r", encoding="utf-8") as handle:
            line = handle.readline(8192)
        obj = json.loads(line)
        if not isinstance(obj, dict) or obj.get("type") == "session.ended":
            return None
        return obj.get("session_id") if isinstance(obj.get("session_id"), str) else None
    except (OSError, ValueError, UnicodeError, TypeError, AttributeError):
        return None


def publish(kind: str, *, session_id: str | None = None, **details: Any) -> None:
    """Escreve um evento leve. Sem acesso à rede, sem nova inferência."""
    if kind not in ALLOWED_TYPES:
        return
    current = session_id or os.environ.get("ORELHAO_MONITOR_SESSION_ID")
    if not current:
        return
    from orelhao.hardware.audit import record_event
    record_event(current, kind, **details)
    path = _file()
    if path is None or _existing_session(path) != current:
        return  # Evita que um worker antigo polua uma chamada nova.
    try:
        encoded = (json.dumps(_event(current, kind, **details),
                              ensure_ascii=False, separators=(",", ":")) + "\n").encode()
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0))
        try:
            if os.fstat(fd).st_size + len(encoded) <= MAX_FILE_BYTES:
                os.write(fd, encoded)
        finally:
            os.close(fd)
    except OSError as exc:
        LOG.debug("Monitor indisponível: %s", exc)


def finish_session(session_id: str, reason: str) -> None:
    """Apaga transcrições/respostas ao encerrar a ligação, preservando só o estado."""
    from orelhao.hardware.audio_diagnostics import close_session
    from orelhao.hardware.audit import record_event
    record_event(session_id, "session.ended", reason=reason)
    close_session(session_id)
    path = _file()
    if path is None or _existing_session(path) != session_id:
        return
    try:
        _replace(path, _event(session_id, "session.ended", reason=reason, status="encerrada"))
    except OSError as exc:
        LOG.debug("Não foi possível limpar a sessão do monitor: %s", exc)
    if len(session_id) == 24 and all(c in "0123456789abcdef" for c in session_id):
        try:
            (path.parent / f"grounding-{session_id}.jsonl").unlink(missing_ok=True)
        except OSError as exc:
            LOG.debug("Não foi possível limpar observações temporárias: %s", exc)


def snapshot() -> dict[str, Any]:
    """Leitura não bloqueante, limitada, para a view web somente leitura."""
    empty: dict[str, Any] = {"session_id": None, "active": False, "events": []}
    path = _file()
    if path is None:
        return empty
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "rb") as handle:
            if os.fstat(handle.fileno()).st_size > MAX_FILE_BYTES:
                return empty
            lines = handle.readlines(MAX_FILE_BYTES + 1)
    except OSError:
        return empty
    events: list[dict[str, Any]] = []
    session_id: str | None = None
    for line in lines[-MAX_EVENTS:]:
        try:
            event = json.loads(line)
        except (json.JSONDecodeError, UnicodeError):
            continue
        if not isinstance(event, dict) or event.get("type") not in ALLOWED_TYPES:
            continue
        if session_id is None:
            session_id = event.get("session_id")
        if event.get("session_id") == session_id:
            events.append(event)
    if not events:
        return empty
    return {
        "session_id": session_id,
        "active": events[-1]["type"] != "session.ended",
        "events": events,
    }
