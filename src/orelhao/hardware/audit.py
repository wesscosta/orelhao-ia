"""Auditoria persistente, local e de baixo custo do atendimento fisico.

Nunca grava audio, resposta gerada ou a transcricao original.
Os temas sao categorias deterministicas; frases redigidas sao opt-in.
"""
from __future__ import annotations

import csv
import io
import logging
import os
import re
import sqlite3
import unicodedata
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

LOG = logging.getLogger(__name__)
METRICS = frozenset({
    "capture_ms", "stt_ms", "rag_ms", "tts_ms", "play_ms", "noise_floor",
    "threshold", "peak_rms", "overflow_count", "false_starts", "speech_detected",
})
ALLOWED_KINDS = frozenset({
    "session.started", "session.ended", "voice.capture", "voice.transcription",
    "voice.transcription_invalid", "voice.response", "voice.error", "voice.playback",
    "voice.idle_timeout",
})
TOPICS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Cursos: saude", ("enfermagem", "saude", "farmacia", "cuidador", "estetica")),
    ("Cursos: tecnologia", ("informatica", "programacao", "tecnologia", "computador",
                            "python", "rede", "excel", "software")),
    ("Cursos: gastronomia", ("gastronomia", "cozinha", "confeitaria", "culinaria")),
    ("Cursos: gestao", ("administracao", "administrativo", "gestao", "contabilidade")),
    ("Cursos: beleza", ("beleza", "cabelo", "maquiagem", "manicure")),
    ("Unidades e enderecos", ("unidade", "endereco", "localizacao", "onde fica", "polo",
                              "parque piaui", "centro", "miguel sady")),
    ("Inscricoes e vagas", ("inscricao", "inscrever", "matricula", "vaga", "turma aberta")),
    ("Valores e bolsas", ("preco", "valor", "quanto custa", "bolsa", "gratuito", "mensalidade")),
    ("Datas e horarios", ("horario", "horas", "data", "quando comeca", "que dia")),
    ("Historia do Senac", ("historia", "oitenta anos", "80 anos", "aniversario senac")),
)
# CPF, telefone, e-mail, CNPJ e sequencias numericas pessoais.
SENSITIVE = re.compile(
    r"(?:\b\d{3}[. ]?\d{3}[. ]?\d{3}[- ]?\d{2}\b"
    r"|\b\d{2}[. ]?\d{3}[. ]?\d{3}[/ ]?\d{4}[- ]?\d{2}\b"
    r"|\b(?:\+?55\s?)?(?:\(?\d{2}\)?\s?)?9?\d{4}[- ]?\d{4}\b"
    r"|\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b"
    r"|\b\d{7,}\b)", re.IGNORECASE,
)
PERSONAL = re.compile(r"\b(meu|meus|minha|minhas|cpf|rg|telefone|celular|email|e-mail|senha|"
                      r"documento|endereco residencial|nome completo|diagnostico|paciente)\b",
                      re.IGNORECASE)


def _normalized(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text.casefold())
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return " ".join(folded.split())


def topic_for(text: str) -> str:
    value = _normalized(text)
    for title, terms in TOPICS:
        if any(term in value for term in terms):
            return title
    if any(term in value for term in ("curso", "formacao", "tecnico")):
        return "Cursos: outros"
    return "Outras duvidas"


def canonical_question(text: str) -> str | None:
    """Pergunta padronizada por intencao, sem armazenar a fala original."""
    topic = topic_for(text)
    value = _normalized(text)
    if topic == "Unidades e enderecos":
        return "Onde fica uma unidade do Senac?"
    if topic == "Inscricoes e vagas":
        return "Como me inscrevo ou consulto vagas?"
    if topic == "Valores e bolsas":
        return "Quanto custa um curso ou como obter bolsa?"
    if topic == "Datas e horarios":
        return "Qual e o horario ou data de inicio?"
    if topic == "Historia do Senac":
        return "Qual e a historia do Senac?"
    if topic.startswith("Cursos:"):
        return "Quais cursos o Senac oferece nessa area?"
    if "curso" in value:
        return "Quais cursos estao disponiveis?"
    return None


def safe_question_label(text: str) -> str | None:
    """Opt-in conservador: rejeita indicadores conhecidos de dados pessoais."""
    value = _normalized(text)
    if not 6 <= len(value) <= 150 or SENSITIVE.search(value) or PERSONAL.search(value):
        return None
    if not re.fullmatch(r"[\w\s?.,!:/()-]+", value):
        return None
    return value[:150]


def database_path() -> Path:
    custom = os.environ.get("ORELHAO_AUDIT_DB")
    if custom:
        return Path(custom).expanduser()
    state = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state")))
    return state / "orelhao-ia" / "audit.sqlite3"


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    if path.is_symlink():
        raise OSError("Arquivo de auditoria nao pode ser link simbolico")
    db = sqlite3.connect(path, timeout=0.08)
    path.chmod(0o600)
    db.execute("PRAGMA busy_timeout=80")
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""
    CREATE TABLE IF NOT EXISTS audit_events(
      id INTEGER PRIMARY KEY,
      at TEXT NOT NULL,
      session TEXT NOT NULL,
      turn INTEGER,
      kind TEXT NOT NULL,
      status TEXT,
      reason TEXT,
      route TEXT,
      topic TEXT,
      question_label TEXT,
      capture_ms REAL,
      stt_ms REAL,
      rag_ms REAL,
      tts_ms REAL,
      play_ms REAL,
      noise_floor REAL,
      threshold REAL,
      peak_rms REAL,
      overflow_count REAL,
      false_starts REAL,
      speech_detected REAL
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_audit_date ON audit_events(at)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_audit_session ON audit_events(session)")
    return db


def record_event(session_id: str, kind: str, **details: Any) -> None:
    if os.environ.get("ORELHAO_AUDIT_ENABLED") != "1" or kind not in ALLOWED_KINDS:
        return
    if not isinstance(session_id, str) or not re.fullmatch(r"[a-f0-9]{24}", session_id):
        return
    metrics = details.get("metrics")
    if not isinstance(metrics, Mapping):
        metrics = {}
    question = details.get("text") if kind == "voice.transcription" else None
    question = question if isinstance(question, str) else None
    topic = topic_for(question) if question else None
    label = None
    if question:
        label = (safe_question_label(question) if
                 os.environ.get("ORELHAO_AUDIT_QUESTION_LABELS") == "1"
                 else canonical_question(question))
    try:
        retention = min(365, max(1, int(os.getenv("ORELHAO_AUDIT_RETENTION_DAYS", "30"))))
    except ValueError:
        retention = 30
    cutoff = (datetime.now(UTC) - timedelta(days=retention)).isoformat()
    now = datetime.now(UTC).isoformat()
    fields = ("capture_ms", "stt_ms", "rag_ms", "tts_ms", "play_ms", "noise_floor",
              "threshold", "peak_rms", "overflow_count", "false_starts", "speech_detected")
    measured = [float(metrics[k]) if isinstance(metrics.get(k), (int, float))
                and not isinstance(metrics.get(k), bool) else None for k in fields]
    try:
        with _connect(database_path()) as db:
            db.execute(
                "INSERT INTO audit_events(at,session,turn,kind,status,reason,route,topic,"
                "question_label," + ",".join(fields) + ") VALUES (?,?,?,?,?,?,?,?,?"
                + ",?" * len(fields) + ")",
                (now, session_id, details.get("turn") if type(details.get("turn")) is int else None,
                 kind, _short(details.get("status")), _short(details.get("reason")),
                 _short(details.get("route")), topic, label, *measured),
            )
            db.execute("DELETE FROM audit_events WHERE at < ?", (cutoff,))
    except (OSError, ValueError, sqlite3.Error) as exc:
        LOG.warning("auditoria_indisponivel: %s", type(exc).__name__)


def _short(value: Any) -> str | None:
    return value[:64] if isinstance(value, str) else None


def summary(*, days: int = 30, path: Path | None = None) -> dict[str, Any]:
    if days < 1 or days > 365:
        raise ValueError("days deve estar entre 1 e 365")
    db_path = path or database_path()
    empty: dict[str, Any] = {
        "days": days, "sessions": 0, "questions": 0, "stt_invalid": 0,
        "capture_without_speech": 0, "abstentions": 0, "errors": 0,
        "topics": [], "questions_top": [], "stt_failures": [],
        "answer_routes": [], "latency_ms": {},
    }
    if not db_path.is_file():
        return empty
    cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    with _connect(db_path) as db:
        def scalar(kind: str, *, predicate: str = "") -> int:
            condition = "AND " + predicate if predicate else ""
            return int(db.execute(
                f"SELECT count(*) FROM audit_events WHERE at >= ? AND kind = ? {condition}",
                (cutoff, kind),
            ).fetchone()[0])

        empty["sessions"] = scalar("session.started")
        empty["questions"] = scalar("voice.transcription")
        empty["stt_invalid"] = scalar("voice.transcription_invalid")
        empty["capture_without_speech"] = scalar(
            "voice.capture", predicate="status='speech_start_timeout' OR speech_detected=0")
        empty["abstentions"] = scalar("voice.response", predicate="status='abstencao'")
        empty["errors"] = scalar("voice.error")
        for result_key, field, kind in (
            ("topics", "topic", "voice.transcription"),
            ("questions_top", "question_label", "voice.transcription"),
            ("stt_failures", "status", "voice.transcription_invalid"),
            ("answer_routes", "route", "voice.response"),
        ):
            data = db.execute(
                f"SELECT {field}, count(*) AS n FROM audit_events "
                f"WHERE at >= ? AND kind=? AND {field} IS NOT NULL "
                f"GROUP BY {field} ORDER BY n DESC, {field} LIMIT 20",
                (cutoff, kind),
            ).fetchall()
            empty[result_key] = [{"label": label, "count": n} for label, n in data]
        latency = db.execute(
            "SELECT avg(capture_ms), avg(stt_ms), avg(rag_ms), avg(tts_ms), avg(play_ms),"
            " sum(coalesce(overflow_count,0)) FROM audit_events WHERE at>=?", (cutoff,),
        ).fetchone()
        empty["latency_ms"] = {
            k: round(float(v), 1) if v is not None else None
            for k, v in zip(("capture", "stt", "rag", "tts", "play", "overflows"), latency)
        }
    return empty


def export_csv(*, days: int = 30, path: Path | None = None) -> str:
    if not 1 <= days <= 365:
        raise ValueError("days deve estar entre 1 e 365")
    db_path = path or database_path()
    output = io.StringIO()
    writer = csv.writer(output)
    cols = ["at", "session", "turn", "kind", "status", "reason", "route", "topic",
            "question_label", "capture_ms", "stt_ms", "rag_ms", "tts_ms", "play_ms",
            "noise_floor", "threshold", "peak_rms", "overflow_count",
            "false_starts", "speech_detected"]
    writer.writerow(cols)
    if not db_path.is_file():
        return output.getvalue()
    cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    with _connect(db_path) as db:
        for values in db.execute(
            "SELECT " + ",".join(cols) + " FROM audit_events WHERE at >= ? "
            "ORDER BY id DESC LIMIT 10000", (cutoff,),
        ):
            # Previne injecao de formulas quando o CSV for aberto no Excel.
            writer.writerow(["'" + v if isinstance(v, str) and v[:1] in ("=", "+", "-", "@")
                             else v for v in values])
    return output.getvalue()
