"""Regressões do ciclo editorial de FAQ e da coleta privada de voz."""
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from orelhao.admin.app import create_admin_app
from orelhao.hardware import audio_diagnostics as audio_diag
from orelhao.hardware import faq
from orelhao.hardware.audit import record_event
from orelhao.hardware.live_monitor import finish_session, start_session
from orelhao.interfaces.voice.audio import PCM16Audio
from orelhao.services.knowledge.index import build_index
from orelhao.services.knowledge.loader import load_documents
from orelhao.services.knowledge.paths import KnowledgePaths

AUTH = ("admin", "long-local-password-for-tests")


@pytest.fixture
def live_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    db = tmp_path / "state" / "audit.sqlite3"
    monkeypatch.setenv("ORELHAO_AUDIT_ENABLED", "1")
    monkeypatch.setenv("ORELHAO_AUDIT_DB", str(db))
    monkeypatch.setenv("ORELHAO_MONITOR_DIR", str(tmp_path / "monitor"))
    monkeypatch.setenv("ORELHAO_AUDIT_PASSWORD", AUTH[1])
    monkeypatch.setenv("ORELHAO_AUDIO_DIAGNOSTICS_DIR", str(tmp_path / "private-audio"))
    monkeypatch.delenv("ORELHAO_AUDIO_DIAGNOSTICS_ENABLED", raising=False)
    return db


def _refusal() -> tuple[str, str]:
    session = "b" * 24
    text = "Quais são os cursos de enfermagem?"
    record_event(session, "voice.transcription", turn=1, text=text, status="reconhecida")
    record_event(session, "voice.response", turn=1, status="abstencao", reason="sem_evidencia")
    return session, text


def test_faq_only_tracks_refusals_after_valid_transcription(live_env: Path) -> None:
    _refusal()
    record_event("a" * 24, "voice.transcription_invalid", turn=1, status="suspeita")
    record_event("c" * 24, "voice.transcription", turn=1, text="Qual o endereço?", status="reconhecida")
    record_event("c" * 24, "voice.response", turn=1, status="respondida")
    rows = faq.candidates(path=live_env)
    assert len(rows) == 1
    assert rows[0]["count"] == 1
    assert rows[0]["topic"] == "Cursos: saude"
    assert rows[0]["status"] == "unreviewed"
    assert "enfermagem" not in live_env.read_text(encoding="latin1")


def test_review_and_publication_are_distinct_and_reindex(tmp_path: Path, live_env: Path) -> None:
    _refusal()
    sources = tmp_path / "knowledge" / "sources"
    sources.mkdir(parents=True)
    (sources / "base.md").write_text("# Instituição\n\nO Senac oferece cursos.", encoding="utf-8")
    paths = KnowledgePaths(sources=sources, index=tmp_path / "knowledge" / "index")
    build_index(paths.sources, paths.index)

    row = faq.candidates(path=live_env)[0]
    review_id = faq.save_review(
        label=row["label"], topic=row["topic"],
        question="Quais cursos existem na área de enfermagem?",
        answer="Consulte a página oficial para confirmar turmas e vagas da área de saúde.",
        source="https://pi.senac.br/",
        path=live_env,
    )
    assert faq.reviews(path=live_env)[0]["status"] == "draft"
    assert len(load_documents(sources)) == 1
    published = faq.publish_review(review_id, paths, path=live_env)
    assert published == f"faq/aprovados/faq-{review_id}.md"
    assert faq.reviews(path=live_env)[0]["status"] == "published"
    assert len(load_documents(sources)) == 2
    assert published in (paths.index / "manifest.json").read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="publicado"):
        faq.save_review(
            label=row["label"], topic=row["topic"], question="Qual novo curso de enfermagem?",
            answer="Resposta substituta longa.", source="https://pi.senac.br/", path=live_env,
        )
    with pytest.raises(ValueError, match="revisões"):
        faq.publish_review(review_id, paths, path=live_env)


def test_failed_reindex_preserves_existing_index_and_draft(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, live_env: Path,
) -> None:
    _refusal()
    sources = tmp_path / "sources"
    sources.mkdir()
    (sources / "base.md").write_text("# Conteúdo\n\nFonte oficial existente.", encoding="utf-8")
    paths = KnowledgePaths(sources=sources, index=tmp_path / "index")
    build_index(paths.sources, paths.index)
    previous = (paths.index / "manifest.json").read_bytes()
    row = faq.candidates(path=live_env)[0]
    review_id = faq.save_review(
        label=row["label"], topic=row["topic"],
        question="Como consultar os cursos da saúde?",
        answer="Informação confirmada pelo supervisor com fonte pública.",
        source="https://pi.senac.br/", path=live_env,
    )

    def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("Falha simulada de indexação")

    monkeypatch.setattr(faq, "build_index", fail)
    with pytest.raises(RuntimeError, match="simulada"):
        faq.publish_review(review_id, paths, path=live_env)
    assert (paths.index / "manifest.json").read_bytes() == previous
    assert len(load_documents(sources)) == 1
    assert faq.reviews(path=live_env)[0]["status"] == "draft"


def test_audio_requires_explicit_arm_and_captures_max_two(
    live_env: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    pcm = PCM16Audio(data=b"\x01\x00" * 16000, sample_rate=16000, channels=1)
    with pytest.raises(ValueError, match="desabilitada"):
        audio_diag.arm_next_session(visitor_informed=True)
    assert not audio_diag.arm_status()
    monkeypatch.setenv("ORELHAO_AUDIO_DIAGNOSTICS_ENABLED", "1")
    with pytest.raises(ValueError, match="Confirme"):
        audio_diag.arm_next_session(visitor_informed=False)
    assert audio_diag.save_sample("d" * 24, 1, pcm, stt_status="recognized") is None
    audio_diag.arm_next_session(visitor_informed=True)
    assert audio_diag.arm_status()
    session = start_session()
    assert not audio_diag.arm_status()
    diagnostic = SimpleNamespace(stop_reason="silence", noise_floor=0.002,
                                 speech_threshold=0.008, peak_rms=0.12)
    a = audio_diag.save_sample(session, 1, pcm, stt_status="recognized", diagnostics=diagnostic)
    b = audio_diag.save_sample(session, 2, pcm, stt_status="empty", diagnostics=diagnostic)
    assert a is not None and b is not None and a != b
    assert audio_diag.save_sample(session, 3, pcm, stt_status="recognized") is None
    samples = audio_diag.list_samples()
    assert len(samples) == 2
    assert samples[0]["sample_rate"] == 16000
    assert samples[0]["peak_rms"] == 0.12
    assert not (audio_diag.sample_path(a).stat().st_mode & 0o077)
    assert not (audio_diag.sample_path(a).parent.stat().st_mode & 0o077)
    assert pcm == PCM16Audio.from_wav_bytes(audio_diag.sample_path(a).read_bytes())
    finish_session(session, "on_hook")
    assert audio_diag.save_sample(session, 4, pcm, stt_status="recognized") is None


def test_audio_retention_and_route_access(
    live_env: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ORELHAO_AUDIO_DIAGNOSTICS_ENABLED", "1")
    client = TestClient(create_admin_app())
    assert client.get("/audit/faq").status_code == 401
    assert client.get("/audit/audio").status_code == 401
    assert client.post("/audit/audio/arm", data={"confirmed": "1"}).status_code == 401
    assert client.post("/audit/audio/arm", data={"confirmed": "0"}, auth=AUTH).status_code == 422
    assert client.post("/audit/audio/arm", data={"confirmed": "1"}, auth=AUTH,
                       headers={"Origin": "https://evil.test"}).status_code == 403
    assert client.post("/audit/audio/arm", data={"confirmed": "1"}, auth=AUTH,
                       follow_redirects=False).status_code == 303
    session = start_session()
    pcm = PCM16Audio(data=b"\x01\x00" * 8000)
    sample = audio_diag.save_sample(session, 1, pcm, stt_status="recognized")
    assert sample is not None
    assert client.get("/audit/audio/sample/" + sample).status_code == 401
    assert client.get("/audit/audio/sample/" + sample, auth=AUTH).status_code == 200
    assert client.get("/audit/audio/sample/../../.env", auth=AUTH).status_code in (404, 422)
    with sqlite3.connect(live_env) as db:
        db.execute("UPDATE audio_samples SET captured_at=?",
                   ((datetime.now(UTC) - timedelta(days=8)).isoformat(),))
    assert audio_diag.list_samples() == []
    assert audio_diag.sample_path(sample) is None
    assert client.get("/audit/audio/sample/" + sample, auth=AUTH).status_code == 404
    assert "FAQ supervisionado" in client.get("/audit/faq", auth=AUTH).text
    assert "Diagnóstico de microfone" in client.get("/audit/audio", auth=AUTH).text


def test_audio_requires_pcm_and_no_automatic_capture(live_env: Path) -> None:
    assert audio_diag.save_sample("d" * 24, 1, PCM16Audio(b"\x01\x00" * 16000),
                                  stt_status="recognized") is None
    assert not (live_env.parent.parent / "private-audio").exists()


def test_faq_admin_route_reviews_and_publishes_explicitly(
    live_env: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from orelhao.admin import learning_routes

    _refusal()
    sources = tmp_path / "knowledge" / "sources"
    sources.mkdir(parents=True)
    paths = KnowledgePaths(sources=sources, index=tmp_path / "knowledge" / "index")
    monkeypatch.setattr(learning_routes, "default_knowledge_paths", lambda: paths)
    row = faq.candidates(path=live_env)[0]
    client = TestClient(create_admin_app(paths=paths))
    payload = {
        "label": row["label"], "topic": row["topic"],
        "question": "Onde consulto as turmas de enfermagem?",
        "answer": "Consulte o catálogo atualizado do Senac Piauí antes da inscrição.",
        "source": "https://pi.senac.br/",
    }
    assert client.post("/audit/faq/review", auth=AUTH, data=payload,
                       headers={"Origin": "https://evil.test"}).status_code == 403
    assert client.post("/audit/faq/review", auth=AUTH, data=payload,
                       follow_redirects=False).status_code == 303
    review_id = faq.reviews(path=live_env)[0]["id"]
    assert not any(sources.rglob("faq-*.md"))
    assert client.post(f"/audit/faq/publish/{review_id}", auth=AUTH,
                       data={"confirmed": "1"},
                       follow_redirects=False).status_code == 303
    assert faq.reviews(path=live_env)[0]["status"] == "published"
    assert any(sources.rglob("faq-*.md"))
    assert "Publicado:" in client.get("/audit/faq", auth=AUTH).text
