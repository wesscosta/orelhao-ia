import json
from pathlib import Path

import numpy as np
import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("multipart")

from fastapi.testclient import TestClient

from orelhao.admin.app import create_admin_app
from orelhao.interfaces.voice.audio import PCM16Audio
from orelhao.services.knowledge.models import Chunk, SearchResult
from orelhao.services.knowledge.observation import ObservationLog, ObservationWorkbench
from orelhao.services.knowledge.paths import KnowledgePaths
from orelhao.services.stt.service import TranscriptionResult


class StubRetriever:
    def search(self, query: str, *, limit: int = 4) -> list[SearchResult]:
        del query, limit
        return [
            SearchResult(
                Chunk("faq:0", "faq", "O atendimento ocorre de segunda a sexta.", "faq.md", 0),
                0.8,
            )
        ]


class StubGenerator:
    def generate(self, question: str, evidence: list[SearchResult]) -> str:
        del question, evidence
        return "O atendimento ocorre de segunda a sexta."


class StubVerifier:
    def support_score(self, query: str, passage: str) -> float:
        del query, passage
        return 0.2


class StubSTT:
    def prepare(self) -> float:
        return 0.0

    def transcribe(self, audio: PCM16Audio) -> TranscriptionResult:
        assert audio.sample_rate == 16_000
        return TranscriptionResult("Qual é o horário?", audio.duration_seconds, 0.01)


class StubTTS:
    def synthesize(self, text: str) -> PCM16Audio:
        assert text
        return PCM16Audio(b"\x00\x00" * 160)


def _client(tmp_path: Path) -> tuple[TestClient, ObservationLog]:
    paths = KnowledgePaths(tmp_path / "sources", tmp_path / "index")
    log = ObservationLog(tmp_path / "observations.jsonl")
    workbench = ObservationWorkbench(
        StubRetriever(), StubGenerator(), StubVerifier(), log
    )
    return TestClient(
        create_admin_app(paths, workbench=workbench, stt=StubSTT(), tts=StubTTS())
    ), log


def test_admin_runs_observation_and_keeps_uncertain_answer(tmp_path: Path) -> None:
    client, log = _client(tmp_path)

    response = client.post("/workbench/run", data={"question": "Qual é o horário?"})

    assert response.status_code == 200
    assert "UNCERTAIN" in response.text
    assert "Modo observação" in response.text
    assert "O atendimento ocorre de segunda a sexta." in response.text
    payload = json.loads(log.path.read_text(encoding="utf-8"))
    assert payload["grounding"]["status"] == "uncertain"


def test_admin_prepares_stt_before_recording(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)

    response = client.get("/workbench")
    assert response.status_code == 200
    for _ in range(20):
        payload = client.get("/workbench/stt-status").json()
        if payload["status"] == "ready":
            break
    assert payload["status"] == "ready"


def test_admin_transcribes_wav_and_synthesizes_answer(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    silence = np.zeros(3_200, dtype=np.int16)
    speech = np.full(8_000, 4_000, dtype=np.int16)
    wav = PCM16Audio(np.concatenate((silence, speech, silence)).tobytes()).to_wav_bytes()

    response = client.post(
        "/workbench/transcribe",
        files={"file": ("question.wav", wav, "audio/wav")},
    )
    assert response.status_code == 200
    assert response.json()["text"] == "Qual é o horário?"

    response = client.get("/workbench/speech/test", params={"text": "Resposta"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"


def test_admin_records_human_rating(tmp_path: Path) -> None:
    client, log = _client(tmp_path)

    response = client.post(
        "/workbench/rate",
        data={
            "observation_id": "abc",
            "rating": "incorrect",
            "grounding_status": "supported",
        },
    )

    assert response.status_code == 200
    payload = json.loads(log.path.read_text(encoding="utf-8"))
    assert payload["event"] == "human_rating"
    assert payload["diagnostic"] == "possible_false_positive"
