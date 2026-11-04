"""Regressoes: privacidade, agregacao e seguranca das rotas de auditoria."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from orelhao.admin.app import create_admin_app
from orelhao.hardware.audit import (
    export_csv,
    record_event,
    safe_question_label,
    summary,
    topic_for,
)
from orelhao.hardware.live_monitor import finish_session, publish, start_session


@pytest.fixture
def audit_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "private" / "audit.sqlite3"
    monkeypatch.setenv("ORELHAO_AUDIT_ENABLED", "1")
    monkeypatch.setenv("ORELHAO_AUDIT_DB", str(db))
    monkeypatch.setenv("ORELHAO_MONITOR_DIR", str(tmp_path / "monitor"))
    monkeypatch.setenv("ORELHAO_AUDIT_RETENTION_DAYS", "30")
    monkeypatch.delenv("ORELHAO_AUDIT_QUESTION_LABELS", raising=False)
    return db


def test_audit_aggregates_stt_rag_and_never_stores_raw_conversation(audit_env: Path) -> None:
    session = start_session()
    publish("voice.capture", session_id=session, turn=1, status="speech_start_timeout",
            metrics={"capture_ms": 3400, "speech_detected": 0, "noise_floor": 0.004,
                     "overflow_count": 2})
    publish("voice.transcription_invalid", session_id=session, turn=1,
            status="sem_fala", text="CPF 123.456.789-00")
    publish("voice.capture", session_id=session, turn=2, status="silence",
            metrics={"capture_ms": 1300, "speech_detected": 1})
    publish("voice.transcription", session_id=session, turn=2,
            text="Quais são os cursos de informática?", status="reconhecida",
            metrics={"stt_ms": 450})
    publish("voice.response", session_id=session, turn=2, status="abstencao",
            reason="sem_evidencia", text="Não tenho essa informação.")
    finish_session(session, "fim")
    result = summary(path=audit_env)
    assert result["sessions"] == 1
    assert result["questions"] == 1
    assert result["stt_invalid"] == 1
    assert result["capture_without_speech"] == 1
    assert result["abstentions"] == 1
    assert result["topics"][0]["label"] == "Cursos: tecnologia"
    assert result["latency_ms"]["stt"] == 450
    assert result["latency_ms"]["overflows"] == 2
    assert result["questions_top"] == [{"label": "Quais cursos o Senac oferece nessa area?", "count": 1}]
    contents = audit_env.read_bytes()
    assert b"123.456" not in contents
    assert "Não tenho essa informação".encode() not in contents
    assert "Quais são os cursos".encode() not in contents
    assert not (audit_env.parent.stat().st_mode & 0o077)
    assert not (audit_env.stat().st_mode & 0o077)


def test_question_labels_opt_in_and_private_content_rejected(
    audit_env: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ORELHAO_AUDIT_QUESTION_LABELS", "1")
    session = start_session()
    publish("voice.transcription", session_id=session, text="Quais cursos na área de saúde?")
    publish("voice.transcription", session_id=session, text="Quais cursos na área de saúde?")
    publish("voice.transcription", session_id=session, text="Meu CPF é 123.456.789-00")
    finish_session(session, "fim")
    result = summary(path=audit_env)
    assert result["questions"] == 3
    assert result["questions_top"] == [{"label": "quais cursos na area de saude?", "count": 2}]
    assert safe_question_label("meu telefone 86999999999") is None
    assert topic_for("Onde fica o polo Parque Piauí?") == "Unidades e enderecos"


def test_disabled_audit_creates_no_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "audit.sqlite3"
    monkeypatch.setenv("ORELHAO_AUDIT_DB", str(db))
    monkeypatch.delenv("ORELHAO_AUDIT_ENABLED", raising=False)
    record_event("a" * 24, "voice.transcription", text="Cursos de tecnologia")
    assert not db.exists()


def test_retention_and_csv_have_no_raw_text(
    audit_env: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    record_event("b" * 24, "voice.transcription", text="Que cursos de informática?")
    import sqlite3

    with sqlite3.connect(audit_env) as conn:
        conn.execute(
            "UPDATE audit_events SET at=?",
            ((datetime.now(UTC) - timedelta(days=40)).isoformat(),),
        )
    record_event("b" * 24, "voice.capture", status="silence")
    assert summary(path=audit_env)["questions"] == 0
    export = export_csv(path=audit_env)
    assert "que cursos de informática?" not in export
    assert "voice.capture" in export


def test_audit_routes_fail_closed_and_restrict_backup_files(
    audit_env: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = tmp_path / "backups"
    directory.mkdir()
    backup = directory / "orelhao-ia-codigo-config-20261103-220933.tar.zst"
    backup.write_bytes(b"TEST BACKUP")
    (directory / "secrets.env").write_text("SECRET", encoding="utf-8")
    (directory / "orelhao-ia-completo-modelos-20261103-220933.tar.zst").symlink_to(
        directory / "secrets.env"
    )
    monkeypatch.setenv("ORELHAO_BACKUP_DIR", str(directory))
    monkeypatch.delenv("ORELHAO_AUDIT_PASSWORD", raising=False)
    client = TestClient(create_admin_app())
    assert client.get("/audit").status_code == 503
    monkeypatch.setenv("ORELHAO_AUDIT_PASSWORD", "secure-phrase-for-local-testing")
    assert client.get("/audit").status_code == 401
    creds = ("admin", "secure-phrase-for-local-testing")
    response = client.get("/audit", auth=creds)
    assert response.status_code == 200
    assert "Auditoria de atendimentos" in response.text
    assert "no-store" in response.headers["cache-control"]
    assert client.get("/audit/summary?days=9999", auth=creds).status_code == 422
    assert client.get("/audit/events.csv", auth=creds).status_code == 200
    names = client.get("/audit/backups", auth=creds).json()["files"]
    assert len(names) == 1 and names[0]["name"] == backup.name
    assert client.get("/audit/backups/" + backup.name, auth=creds).content == b"TEST BACKUP"
    assert client.get("/audit/backups/secrets.env", auth=creds).status_code == 404


def test_audit_rejects_remote_clients(audit_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORELHAO_AUDIT_PASSWORD", "secure-phrase-for-local-testing")
    with TestClient(create_admin_app(), base_url="http://public.example"):
        # TestClient emite "testclient"; simular o cliente real via ASGI scope.
        from starlette.requests import Request

        from orelhao.admin.audit_routes import _admin_only

        request = Request({"type": "http", "method": "GET", "scheme": "http", "path": "/audit",
                           "headers": [], "query_string": b"", "client": ("10.0.0.8", 42222),
                           "server": ("0.0.0.0", 8000)})
        from fastapi import HTTPException
        from fastapi.security import HTTPBasicCredentials
        with pytest.raises(HTTPException) as err:
            _admin_only(request, HTTPBasicCredentials(
                username="admin", password="secure-phrase-for-local-testing"))
        assert err.value.status_code == 403
