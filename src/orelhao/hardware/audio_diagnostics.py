"""Amostras WAV de diagnóstico com autorização administrativa por sessão.

Desligado por padrão, sem transcrições e com retenção curta. A coleta deve ser
precedida por informação e autorização aplicável ao visitante.
"""
from __future__ import annotations

import logging
import os
import re
import secrets
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from orelhao.hardware.audit import _connect, database_path
from orelhao.interfaces.voice.audio import PCM16Audio

LOG = logging.getLogger(__name__)
SESSION_RE = re.compile(r"[a-f0-9]{24}\Z")
SAMPLE_RE = re.compile(r"[a-f0-9]{32}\Z")


def enabled() -> bool:
    return os.getenv("ORELHAO_AUDIO_DIAGNOSTICS_ENABLED") == "1"


def _directory() -> Path:
    root = os.getenv("ORELHAO_AUDIO_DIAGNOSTICS_DIR")
    if root:
        path = Path(root).expanduser()
    else:
        path = database_path().parent / "audio-diagnostics"
    if path.is_symlink():
        raise OSError("Diretório de áudio não pode ser link simbólico")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)
    return path


def _init(db: sqlite3.Connection) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS audio_arm(
        id INTEGER PRIMARY KEY CHECK(id=1), expires_at TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS audio_allowed_sessions(
        session TEXT PRIMARY KEY, expires_at TEXT NOT NULL, remaining INTEGER NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS audio_samples(
        id TEXT PRIMARY KEY, session TEXT NOT NULL, turn INTEGER NOT NULL,
        captured_at TEXT NOT NULL, duration_seconds REAL NOT NULL,
        stt_status TEXT NOT NULL, capture_status TEXT,
        noise_floor REAL, threshold REAL, peak_rms REAL, sample_rate INTEGER NOT NULL
    )""")


def arm_next_session(*, visitor_informed: bool, minutes: int = 5) -> None:
    """O gestor confirma que informou e obteve autorização para o próximo teste."""
    if not enabled():
        raise ValueError("Captura diagnóstica desabilitada no servidor")
    if not visitor_informed or not 1 <= minutes <= 10:
        raise ValueError("Confirme informação e autorização antes de ativar")
    expires = (datetime.now(UTC) + timedelta(minutes=minutes)).isoformat()
    with _connect(database_path()) as db:
        _init(db)
        db.execute("INSERT OR REPLACE INTO audio_arm(id, expires_at) VALUES(1,?)", (expires,))


def disarm() -> None:
    db_path = database_path()
    if db_path.is_file():
        with _connect(db_path) as db:
            _init(db)
            db.execute("DELETE FROM audio_arm")


def arm_status() -> bool:
    if not enabled() or not database_path().is_file():
        return False
    with _connect(database_path()) as db:
        _init(db)
        row = db.execute("SELECT expires_at FROM audio_arm WHERE id=1").fetchone()
        return bool(row and row[0] > datetime.now(UTC).isoformat())


def authorize_started_session(session_id: str) -> None:
    if not enabled() or not SESSION_RE.fullmatch(session_id) or not database_path().is_file():
        return
    now = datetime.now(UTC).isoformat()
    try:
        with _connect(database_path()) as db:
            _init(db)
            row = db.execute("SELECT expires_at FROM audio_arm WHERE id=1").fetchone()
            if row is None:
                return
            db.execute("DELETE FROM audio_arm WHERE id=1")
            if row[0] > now:
                db.execute(
                    "INSERT OR IGNORE INTO audio_allowed_sessions(session,expires_at,remaining)"
                    " VALUES (?,?,2)", (session_id, row[0]),
                )
    except sqlite3.Error:
        LOG.warning("Falha ao registrar sessão de diagnóstico")


def close_session(session_id: str) -> None:
    if not SESSION_RE.fullmatch(session_id) or not database_path().is_file():
        return
    try:
        with _connect(database_path()) as db:
            _init(db)
            db.execute("DELETE FROM audio_allowed_sessions WHERE session=?", (session_id,))
    except sqlite3.Error:
        LOG.warning("Falha ao encerrar autorização de áudio")


def _retention_days() -> int:
    try:
        return min(14, max(1, int(os.getenv("ORELHAO_AUDIO_RETENTION_DAYS", "7"))))
    except ValueError:
        return 7


def _prune(db: sqlite3.Connection, folder: Path) -> None:
    cutoff = (datetime.now(UTC) - timedelta(days=_retention_days())).isoformat()
    for (sample_id,) in db.execute(
        "SELECT id FROM audio_samples WHERE captured_at < ?", (cutoff,)
    ).fetchall():
        (folder / (sample_id + ".wav")).unlink(missing_ok=True)
    db.execute("DELETE FROM audio_samples WHERE captured_at < ?", (cutoff,))
    db.execute(
        "DELETE FROM audio_allowed_sessions WHERE expires_at < ?",
        (datetime.now(UTC).isoformat(),),
    )


def save_sample(
    session_id: str, turn: int, audio: PCM16Audio, *,
    stt_status: str, diagnostics: Any = None,
) -> str | None:
    """No máximo duas amostras por sessão autorizada; falhas não bloqueiam a chamada."""
    if (not enabled() or not SESSION_RE.fullmatch(session_id)
            or type(turn) is not int or turn < 1
            or not isinstance(audio, PCM16Audio)
            or audio.channels != 1 or not 8000 <= audio.sample_rate <= 48000
            or not 0.2 <= audio.duration_seconds <= 30
            or len(audio.data) > 2_880_000):
        return None
    sample_id = secrets.token_hex(16)
    filename: Path | None = None
    try:
        folder = _directory()
        with _connect(database_path()) as db:
            _init(db)
            _prune(db, folder)
            cursor = db.execute(
                "UPDATE audio_allowed_sessions SET remaining=remaining-1"
                " WHERE session=? AND remaining>0 AND expires_at>?",
                (session_id, datetime.now(UTC).isoformat()),
            )
            if not cursor.rowcount:
                return None
            filename = folder / (sample_id + ".wav")
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            fd = os.open(filename, flags, 0o600)
            with os.fdopen(fd, "wb") as handle:
                handle.write(audio.to_wav_bytes())
                handle.flush()
                os.fsync(handle.fileno())
            def metric(name: str) -> float | None:
                value = getattr(diagnostics, name, None)
                return (float(value) if isinstance(value, (float, int))
                        and not isinstance(value, bool) else None)
            db.execute(
                "INSERT INTO audio_samples VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (sample_id, session_id, turn, datetime.now(UTC).isoformat(),
                 round(audio.duration_seconds, 3), stt_status[:30],
                 str(getattr(diagnostics, "stop_reason", ""))[:40],
                 metric("noise_floor"), metric("speech_threshold"),
                 metric("peak_rms"), audio.sample_rate),
            )
        return sample_id
    except (OSError, sqlite3.Error, ValueError) as exc:
        if filename is not None:
            filename.unlink(missing_ok=True)
        LOG.warning("amostra_audio_indisponivel: %s", type(exc).__name__)
        return None


def list_samples() -> list[dict[str, Any]]:
    if not database_path().is_file():
        return []
    folder = _directory()
    with _connect(database_path()) as db:
        _init(db)
        _prune(db, folder)
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute(
            "SELECT id,turn,captured_at,duration_seconds,stt_status,capture_status,"
            "noise_floor,threshold,peak_rms,sample_rate FROM audio_samples "
            "ORDER BY captured_at DESC LIMIT 50"
        )]


def sample_path(sample_id: str) -> Path | None:
    if not SAMPLE_RE.fullmatch(sample_id) or not database_path().is_file():
        return None
    with _connect(database_path()) as db:
        _init(db)
        _prune(db, _directory())
        row = db.execute("SELECT 1 FROM audio_samples WHERE id=?", (sample_id,)).fetchone()
    if not row:
        return None
    filename = _directory() / (sample_id + ".wav")
    if filename.is_symlink() or not filename.is_file():
        return None
    return filename
