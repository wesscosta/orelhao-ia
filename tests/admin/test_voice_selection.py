from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from orelhao.admin.app import create_admin_app
from orelhao.interfaces.voice.audio import PCM16Audio
from orelhao.services.knowledge.observation import (
    ObservationLog,
    ObservationWorkbench,
)
from orelhao.services.knowledge.paths import KnowledgePaths


class Retriever:
    def search(self, query: str, *, limit: int = 8) -> list[object]:
        del query, limit
        return []


class Generator:
    def generate(self, question: str, evidence: list[object]) -> str:
        del question, evidence
        return "Eu sou o Lumi, assistente virtual."


class Verifier:
    def support_score(self, query: str, passage: str) -> float:
        del query, passage
        return 0.99


class VoiceSpy:
    def __init__(self, sample: int) -> None:
        self.sample = sample
        self.spoken: list[str] = []

    def synthesize(self, text: str) -> PCM16Audio:
        self.spoken.append(text)
        return PCM16Audio(
            self.sample.to_bytes(2, "little", signed=True) * 500,
            sample_rate=22_050,
        )

    def validate(self) -> None:
        return None


def _test_client(tmp_path: Path) -> tuple[TestClient, ObservationLog, VoiceSpy, VoiceSpy]:
    cadu = VoiceSpy(123)
    faber = VoiceSpy(456)
    log = ObservationLog(tmp_path / "voices.jsonl")
    bench = ObservationWorkbench(Retriever(), Generator(), Verifier(), log)
    client = TestClient(create_admin_app(
        KnowledgePaths(tmp_path / "sources", tmp_path / "index"),
        workbench=bench,
        tts_voices={"cadu": cadu, "faber": faber},
    ))
    return client, log, cadu, faber


def test_selector_is_available_on_both_workbench_pages(tmp_path: Path) -> None:
    client, log, _, _ = _test_client(tmp_path)
    html = client.get("/workbench").text
    assert 'id="voice"' in html
    assert 'value="cadu"' in html and 'value="faber"' in html
    assert "Ouvir apresentação do Lumi" in html

    result = client.post("/workbench/run", data={
        "question": "Quem é você?", "mode": "enforce", "voice": "faber",
    })
    assert result.status_code == 200
    assert 'id="result-voice"' in result.text
    assert '<option value="faber" selected>' in result.text
    assert "/workbench/speech/" in result.text
    assert json.loads(log.path.read_text())["presented_answer"]


def test_voices_change_for_same_observation_without_reexecuting_llm(
    tmp_path: Path,
) -> None:
    client, log, cadu, faber = _test_client(tmp_path)
    response = client.post("/workbench/run", data={
        "question": "Quem é você?", "mode": "observe", "voice": "cadu",
    })
    assert response.status_code == 200
    observation = json.loads(log.path.read_text())
    speech = "/workbench/speech/" + observation["observation_id"]
    cadu_response = client.get(speech, params={"voice": "cadu"})
    faber_response = client.get(speech, params={"voice": "faber"})
    assert cadu_response.status_code == faber_response.status_code == 200
    assert cadu_response.content != faber_response.content
    assert cadu_response.headers["X-Orelhao-Voice"] == "cadu"
    assert faber_response.headers["X-Orelhao-Voice"] == "faber"
    assert cadu.spoken == [observation["presented_answer"]]
    assert faber.spoken == [observation["presented_answer"]]
    assert len(log.path.read_text().splitlines()) == 1


def test_preview_uses_fixed_masculine_identity_and_whitelisted_voice(
    tmp_path: Path,
) -> None:
    client, _, cadu, faber = _test_client(tmp_path)
    result = client.get("/workbench/voice-preview", params={
        "voice": "faber", "text": "O dado é falso."
    })
    assert result.status_code == 200
    assert result.headers["content-type"] == "audio/wav"
    assert result.headers["X-Orelhao-Voice"] == "faber"
    assert "Eu sou o Lumi" in faber.spoken[0]
    assert "O dado é falso" not in faber.spoken[0]
    assert cadu.spoken == []


def test_voice_validation_and_status_fail_closed(tmp_path: Path) -> None:
    client, log, cadu, faber = _test_client(tmp_path)
    for voice in ("../models/anything", "Faber", "kokoro"):
        status = client.get("/workbench/tts-status", params={"voice": voice})
        assert status.status_code == 200 and not status.json()["available"]
        assert client.get("/workbench/voice-preview", params={"voice": voice}).status_code == 422
        assert client.post("/workbench/run", data={
            "question": "Teste?", "voice": voice
        }).status_code == 422
        assert client.get(
            "/workbench/speech/" + "f" * 32, params={"voice": voice}
        ).status_code == 422
    assert not log.path.exists()
    assert cadu.spoken == faber.spoken == []
    for voice in ("cadu", "faber"):
        status = client.get("/workbench/tts-status", params={"voice": voice}).json()
        assert status["available"] and status["voice"] == voice
