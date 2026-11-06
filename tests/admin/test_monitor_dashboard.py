"""A interface web espelha apenas eventos da sessão física ativa."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

from orelhao.admin.app import create_admin_app
from orelhao.hardware.live_monitor import finish_session, publish, start_session


def test_monitor_page_and_readonly_snapshot(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ORELHAO_MONITOR_DIR", str(tmp_path))
    app = create_admin_app()
    with TestClient(app) as client:
        page = client.get("/monitor")
        assert page.status_code == 200
        assert "Monitor de Atendimento" in page.text
        assert '/static/js/monitor.js' in page.text
        script = client.get("/static/js/monitor.js")
        assert script.status_code == 200
        assert "new EventSource('/monitor/events')" in script.text
        assert "Cache-Control" in page.headers

        empty = client.get("/monitor/state")
        assert empty.status_code == 200
        assert empty.json()["active"] is False

        session = start_session()
        publish("voice.transcription", session_id=session, turn=1,
                text="<script>não executar</script>")
        state = client.get("/monitor/state")
        assert state.json()["session_id"] == session
        assert state.json()["events"][-1]["text"] == "<script>não executar</script>"
        # A UI usa textContent para inserir a transcrição, não innerHTML.
        assert "content.textContent = ev.text" in script.text
        assert "innerHTML" not in script.text
        finish_session(session, "desligou")
        assert client.get("/monitor/state").json()["events"][0]["type"] == "session.ended"


def test_sse_emits_valid_event_stream(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ORELHAO_MONITOR_DIR", str(tmp_path))
    session = start_session()
    publish("voice.response", session_id=session, text="Olá")
    app = create_admin_app()
    endpoint = next(r.endpoint for r in app.routes if getattr(r, "path", None) == "/monitor/events")

    class Connected:
        async def is_disconnected(self) -> bool:
            return False

    async def first_event() -> str:
        response = await endpoint(Connected())
        assert response.media_type == "text/event-stream"
        iterator = response.body_iterator
        try:
            return await anext(iterator)
        finally:
            await iterator.aclose()

    event = asyncio.run(first_event())
    assert event.startswith("data: ")
    assert event.endswith("\n\n")
    payload = json.loads(event.removeprefix("data: ").strip())
    assert payload["session_id"] == session
    assert payload["events"][-1]["text"] == "Olá"
