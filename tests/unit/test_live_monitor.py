"""Contrato de eventos leves da chamada física e descarte de transcrições."""
from __future__ import annotations

import json
import stat
from pathlib import Path

from orelhao.hardware import live_monitor


def test_live_session_publishes_and_removes_transcripts_on_hangup(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("ORELHAO_MONITOR_DIR", str(tmp_path))
    monkeypatch.delenv("ORELHAO_MONITOR_SESSION_ID", raising=False)
    assert live_monitor.snapshot()["events"] == []

    sid = live_monitor.start_session()
    monkeypatch.setenv("ORELHAO_MONITOR_SESSION_ID", sid)
    live_monitor.publish("voice.transcription", turn=1, text="Quais são os cursos?")
    live_monitor.publish("voice.response", turn=1, text="Cursos técnicos.",
                         route="guided", status="respondida",
                         metrics={"rag_ms": 10.2345})
    data = live_monitor.snapshot()
    assert data["active"] is True
    assert data["session_id"] == sid
    assert data["events"][1]["text"] == "Quais são os cursos?"
    assert data["events"][2]["metrics"]["rag_ms"] == 10.23

    file = tmp_path / live_monitor.FILE_NAME
    assert stat.S_IMODE(file.stat().st_mode) == 0o600
    live_monitor.finish_session(sid, "contato_aberto")
    closed = live_monitor.snapshot()
    assert closed["active"] is False
    assert closed["events"] == [
        closed["events"][0]
    ]
    assert closed["events"][0]["type"] == "session.ended"
    assert "Quais são os cursos?" not in file.read_text()
    live_monitor.publish("voice.transcription", text="Atrasado")
    assert live_monitor.snapshot() == closed


def test_new_session_discards_prior_session_and_rejects_old_worker(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("ORELHAO_MONITOR_DIR", str(tmp_path))
    one = live_monitor.start_session()
    live_monitor.publish("voice.transcription", session_id=one, text="Primeira ligação")
    two = live_monitor.start_session()
    live_monitor.publish("voice.transcription", session_id=one, text="Chegou atrasado")
    live_monitor.publish("voice.transcription", session_id=two, text="Segunda ligação")
    state = live_monitor.snapshot()
    assert state["session_id"] == two
    assert [e.get("text") for e in state["events"] if "text" in e] == ["Segunda ligação"]


def test_events_are_whitelisted_and_bounded(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ORELHAO_MONITOR_DIR", str(tmp_path))
    sid = live_monitor.start_session()
    live_monitor.publish("malicious.kind", session_id=sid, text="Não entra")
    live_monitor.publish("voice.transcription", session_id=sid, text="x" * 5000)
    state = live_monitor.snapshot()
    assert len(state["events"]) == 2
    assert len(state["events"][1]["text"]) == live_monitor.MAX_TEXT
    line = (tmp_path / live_monitor.FILE_NAME).read_text().splitlines()[1]
    assert json.loads(line)["type"] == "voice.transcription"


def test_transcript_not_written_without_session(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ORELHAO_MONITOR_DIR", str(tmp_path))
    monkeypatch.delenv("ORELHAO_MONITOR_SESSION_ID", raising=False)
    live_monitor.publish("voice.transcription", text="Teste")
    assert not (tmp_path / live_monitor.FILE_NAME).exists()


def test_hook_starts_same_monitored_session_used_by_worker(
    tmp_path: Path, monkeypatch
) -> None:
    from orelhao.hardware import hook_runtime
    from orelhao.hardware.serial_hook import HookEvent

    monkeypatch.setenv("ORELHAO_MONITOR_DIR", str(tmp_path))
    spawned: list[dict] = []

    class FakeProc:
        pid = 999_123

        def poll(self):
            return None

    def fake_popen(*args, **kwargs):
        spawned.append(kwargs)
        return FakeProc()

    monkeypatch.setattr(hook_runtime.subprocess, "Popen", fake_popen)
    process = hook_runtime.spawn_voice()
    sid = spawned[0]["env"]["ORELHAO_MONITOR_SESSION_ID"]
    assert live_monitor.snapshot()["session_id"] == sid

    live_monitor.publish("voice.transcription", session_id=sid, text="Teste do monofone")
    assert live_monitor.snapshot()["events"][-1]["text"] == "Teste do monofone"

    ctl = hook_runtime.HookCallController(
        spawn=lambda: process, stop=lambda _proc: None, ready=lambda: True
    )
    ctl.handle(HookEvent("state", "open", 1, 0, 27))
    ctl.handle(HookEvent("change", "closed", 2, 1000, 27))
    assert ctl._pending_since is not None
    ctl._pending_since -= 1
    ctl.check()
    ctl.handle(HookEvent("change", "open", 3, 2000, 27))
    finished = live_monitor.snapshot()
    assert not finished["active"]
    assert finished["events"][0]["type"] == "session.ended"
    assert "Teste do monofone" not in (tmp_path / live_monitor.FILE_NAME).read_text()



def test_voice_grounding_log_is_removed_at_hangup(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ORELHAO_MONITOR_DIR", str(tmp_path))
    sid = live_monitor.start_session()
    monkeypatch.setenv("ORELHAO_MONITOR_SESSION_ID", sid)
    log = live_monitor.voice_observation_log_path()
    assert log is not None
    log.write_text('{"question":"Dado de teste"}', encoding="utf-8")
    live_monitor.publish("voice.context", text="Pergunta reescrita", turn=2)
    assert live_monitor.snapshot()["events"][-1]["type"] == "voice.context"
    live_monitor.finish_session(sid, "contato_aberto")
    assert not log.exists()
    assert not live_monitor.snapshot()["active"]


def test_invalid_session_cannot_choose_observation_log(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ORELHAO_MONITOR_DIR", str(tmp_path))
    monkeypatch.setenv("ORELHAO_MONITOR_SESSION_ID", "../outra/sessao")
    assert live_monitor.voice_observation_log_path() is None
