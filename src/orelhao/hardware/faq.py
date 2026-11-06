"""FAQ supervisionado derivado da auditoria anônima. Nunca aprende respostas sozinho."""
from __future__ import annotations

import shutil
import sqlite3
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from orelhao.hardware.audit import _connect, database_path
from orelhao.services.knowledge.index import build_index
from orelhao.services.knowledge.paths import KnowledgePaths


def _init(db: sqlite3.Connection) -> None:
    db.execute("""
    CREATE TABLE IF NOT EXISTS faq_reviews (
        id INTEGER PRIMARY KEY,
        label TEXT NOT NULL,
        topic TEXT NOT NULL,
        question TEXT NOT NULL,
        answer TEXT NOT NULL,
        source TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'draft',
        updated_at TEXT NOT NULL,
        published_path TEXT,
        UNIQUE(label, topic)
    )""")


def candidates(*, days: int = 30, path: Path | None = None) -> list[dict[str, Any]]:
    """Grupos com abstenção após STT válido; não confundem falha de áudio com lacuna RAG."""
    if not 1 <= days <= 365:
        raise ValueError("Período inválido")
    db_path = path or database_path()
    if not db_path.is_file():
        return []
    cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    with _connect(db_path) as db:
        _init(db)
        records = db.execute("""
            SELECT q.question_label, q.topic, COUNT(DISTINCT q.id) AS total,
                   MAX(q.at) AS last_seen, COALESCE(f.status, 'unreviewed')
            FROM audit_events q
            JOIN audit_events r ON r.session=q.session AND r.turn=q.turn
                AND r.kind='voice.response' AND r.status='abstencao'
            LEFT JOIN faq_reviews f ON f.label=q.question_label AND f.topic=q.topic
            WHERE q.kind='voice.transcription' AND q.at >= ?
                AND q.question_label IS NOT NULL AND q.topic IS NOT NULL
            GROUP BY q.question_label, q.topic
            ORDER BY total DESC, last_seen DESC LIMIT 100
        """, (cutoff,)).fetchall()
    return [
        {"label": a, "topic": b, "count": n, "last_seen": when, "status": status}
        for a, b, n, when, status in records
    ]


def reviews(*, path: Path | None = None) -> list[dict[str, Any]]:
    db_path = path or database_path()
    if not db_path.is_file():
        return []
    with _connect(db_path) as db:
        _init(db)
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute(
            "SELECT * FROM faq_reviews ORDER BY updated_at DESC LIMIT 100"
        )]


def save_review(
    *, label: str, topic: str, question: str, answer: str, source: str,
    path: Path | None = None,
) -> int:
    """Supervisor propõe a resposta. A revisão NÃO altera o índice ativo."""
    label, topic = label.strip(), topic.strip()
    question, answer, source = question.strip(), answer.strip(), source.strip()
    if not (5 <= len(label) <= 150 and 3 <= len(topic) <= 80):
        raise ValueError("Grupo de pergunta inválido")
    if not (10 <= len(question) <= 240 and 10 <= len(answer) <= 1600):
        raise ValueError("Pergunta ou resposta fora do limite")
    if ("\n" in question or not source.startswith("https://")
            or not 12 <= len(source) <= 700 or any(c.isspace() for c in source)):
        raise ValueError("Forneça pergunta em uma linha e URL HTTPS da fonte")
    db_path = path or database_path()
    if not db_path.is_file():
        raise ValueError("Nenhuma auditoria disponível")
    allowed = {(r["label"], r["topic"]) for r in candidates(path=db_path, days=365)}
    if (label, topic) not in allowed:
        raise ValueError("A pendência deve existir na auditoria")
    now = datetime.now(UTC).isoformat()
    with _connect(db_path) as db:
        _init(db)
        existing = db.execute(
            "SELECT id, status FROM faq_reviews WHERE label=? AND topic=?",
            (label, topic),
        ).fetchone()
        if existing is not None and existing[1] == "published":
            raise ValueError("FAQ publicado é imutável nesta versão")
        db.execute("""
            INSERT INTO faq_reviews(label,topic,question,answer,source,status,updated_at)
            VALUES (?,?,?,?,?,'draft',?)
            ON CONFLICT(label,topic) DO UPDATE SET
                question=excluded.question, answer=excluded.answer,
                source=excluded.source, status='draft', updated_at=excluded.updated_at
        """, (label, topic, question, answer, source, now))
        return int(db.execute(
            "SELECT id FROM faq_reviews WHERE label=? AND topic=?", (label, topic)
        ).fetchone()[0])


def _promote_index(paths: KnowledgePaths) -> None:
    """Constrói índice completo em staging, preservando o anterior se falhar."""
    paths.index.parent.mkdir(parents=True, exist_ok=True)
    if paths.index.is_symlink():
        raise ValueError("Índice não pode ser link simbólico")
    staging = Path(tempfile.mkdtemp(prefix=".faq-reindex-", dir=paths.index.parent))
    prior = staging / "previous"
    try:
        generated = staging / "generated"
        build_index(paths.sources, generated)
        had_previous = paths.index.exists()
        if had_previous:
            paths.index.rename(prior)
        try:
            generated.rename(paths.index)
        except OSError:
            if had_previous:
                prior.rename(paths.index)
            raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def publish_review(
    review_id: int, paths: KnowledgePaths, *, path: Path | None = None,
) -> str:
    """Publicação humana explícita; arquivo e índice testados antes da promoção."""
    from orelhao.admin.source_manager import atomic_write_source

    if review_id < 1:
        raise ValueError("Identificador inválido")
    db_path = path or database_path()
    with _connect(db_path) as db:
        _init(db)
        item = db.execute(
            "SELECT question,answer,source,status FROM faq_reviews WHERE id=?",
            (review_id,),
        ).fetchone()
        if item is None or item[3] != "draft":
            raise ValueError("Somente revisões não publicadas podem ser promovidas")
        question, answer, source, _ = item
        relative = f"faq/aprovados/faq-{review_id}.md"
        target = paths.sources / relative
        if target.exists() or target.is_symlink():
            raise ValueError("Documento FAQ já existe; publicação cancelada")
        metadata = yaml.safe_dump({
            "title": question, "category": "faq", "authority": "supervisor-approved",
            "source_url": source, "reviewed_at": datetime.now(UTC).date().isoformat(),
        }, allow_unicode=True, sort_keys=False)
        contents = f"---\n{metadata}---\n\n# {question}\n\n{answer}\n\nFonte: {source}\n"
        atomic_write_source(paths.sources, relative, contents)
        try:
            _promote_index(paths)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        db.execute(
            "UPDATE faq_reviews SET status='published', published_path=?, updated_at=? WHERE id=?",
            (relative, datetime.now(UTC).isoformat(), review_id),
        )
        return relative
