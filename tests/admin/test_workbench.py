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
    assert "Fact Validator V3" in response.text
    assert "Nenhum atributo tipado identificado." in response.text
    assert "Trecho candidato" in response.text
    assert "cobertura lexical" in response.text
    payload = json.loads(log.path.read_text(encoding="utf-8"))
    assert payload["claims"][0]["span_selection"]["support_verified"] is False
    assert payload["claims"][0]["span_selection"]["span"]["source"] == "faq.md"
    assert payload["claims"][0]["span_selection"]["span"]["text"] == (
        "O atendimento ocorre de segunda a sexta."
    )
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
    llm_status = client.get("/workbench/llm-status").json()
    assert llm_status["available"]
    assert 'id="tts-status"' in response.text


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

    result = client.post("/workbench/run", data={"question": "Qual é o horário?"})
    assert result.status_code == 200
    assert "Ouvir resposta" in result.text
    assert "spoken-status" in result.text
    observation = json.loads((tmp_path / "observations.jsonl").read_text(encoding="utf-8"))
    response = client.get(f"/workbench/speech/{observation['observation_id']}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.headers["cache-control"] == "no-store"
    assert response.content.startswith(b"RIFF")


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


def test_admin_safe_policy_blocks_unsupported_answer(tmp_path: Path) -> None:
    client, log = _client(tmp_path)
    response = client.post(
        "/workbench/run",
        data={"question": "Qual é o horário?", "mode": "enforce"},
    )
    assert response.status_code == 200
    assert "Modo seguro" in response.text
    assert "Verificação por afirmação" in response.text
    assert "Não encontrei evidências suficientes" in response.text
    logged = json.loads(log.path.read_text(encoding="utf-8"))
    assert logged["mode"] == "enforce"
    assert logged["presented_answer"] != logged["answer"]


def test_admin_rejects_invalid_policy(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    response = client.post(
        "/workbench/run",
        data={"question": "Qual é o horário?", "mode": "invalid"},
    )
    assert response.status_code == 422

def test_workbench_tts_status_and_rejects_arbitrary_speech(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    status = client.get("/workbench/tts-status")
    assert status.status_code == 200
    assert status.json()["available"] is True

    invalid = client.get("/workbench/speech/unknown", params={"text": "não autorizado"})
    assert invalid.status_code == 404
    missing = client.get("/workbench/speech/" + "f" * 32)
    assert missing.status_code == 404


def test_workbench_speech_uses_presented_answer_in_safe_mode(tmp_path: Path) -> None:
    client, log = _client(tmp_path)
    result = client.post(
        "/workbench/run",
        data={"question": "Qual é o horário?", "mode": "enforce"},
    )
    assert result.status_code == 200
    observation = json.loads(log.path.read_text(encoding="utf-8"))
    assert observation["presented_answer"] != observation["answer"]
    assert log.presented_answer_for(observation["observation_id"]) == observation["presented_answer"]
    response = client.get(f"/workbench/speech/{observation['observation_id']}")
    assert response.status_code == 200



def test_admin_precheck_enforce_blocks_llm_and_tts_reads_only_safe_answer(
    tmp_path: Path,
) -> None:
    from orelhao.services.knowledge.answerability import EvidenceAdjudicator

    class NeverGenerator:
        def generate(self, question: str, evidence: list[SearchResult]) -> str:
            raise AssertionError("LLM não deve ser chamada sem evidência atual")

    log = ObservationLog(tmp_path / "observations.jsonl")
    workbench = ObservationWorkbench(
        StubRetriever(), NeverGenerator(), StubVerifier(), log,
        adjudicator=EvidenceAdjudicator(),
    )
    paths = KnowledgePaths(tmp_path / "sources", tmp_path / "index")
    client = TestClient(create_admin_app(
        paths, workbench=workbench, stt=StubSTT(), tts=StubTTS()
    ))
    response = client.post(
        "/workbench/run",
        data={"question": "Há vagas disponíveis hoje?", "mode": "enforce"},
    )
    assert response.status_code == 200
    assert "Answerability pré-geração" in response.text
    assert "temporal_evidence_unavailable" in response.text
    assert "geração ignorada: true" in response.text
    assert "entidade incorreta na resposta: false" in response.text
    row = json.loads(log.path.read_text(encoding="utf-8"))
    assert row["generation_skipped"]
    assert row["answerability"]["reason"] == "temporal_evidence_unavailable"
    assert client.get(
        f"/workbench/speech/{row['observation_id']}"
    ).status_code == 200



def test_admin_v3_blocks_wrong_numeric_answer_and_speaks_only_safe_text(
    tmp_path: Path,
) -> None:
    class ExcelRetriever:
        def search(self, query: str, *, limit: int = 8) -> list[SearchResult]:
            del query, limit
            return [SearchResult(Chunk(
                "excel:0", "excel", "O curso Excel tem 30 horas.",
                "excel.md", 0, {
                    "entity_id": "curso:excel", "authority": "primary",
                    "source_url": "https://example.org/excel",
                },
            ), 0.94)]

    class WrongLLM:
        def generate(self, question: str, evidence: list[SearchResult]) -> str:
            del question, evidence
            return "O curso Excel tem 60 horas."

    class BadNLI:
        def support_score(self, query: str, passage: str) -> float:
            del query, passage
            return 0.99

    class RecordingTTS:
        def __init__(self) -> None:
            self.texts: list[str] = []

        def synthesize(self, text: str) -> PCM16Audio:
            self.texts.append(text)
            return PCM16Audio(b"\x00\x00" * 160)

    log = ObservationLog(tmp_path / "observations-v3.jsonl")
    tts = RecordingTTS()
    workbench = ObservationWorkbench(
        ExcelRetriever(), WrongLLM(), BadNLI(), log,
    )
    client = TestClient(create_admin_app(
        KnowledgePaths(tmp_path / "sources", tmp_path / "index"),
        workbench=workbench, stt=StubSTT(), tts=tts,
    ))
    result = client.post("/workbench/run", data={
        "question": "Qual a carga horária de Excel?", "mode": "enforce",
    })
    assert result.status_code == 200
    assert "Grounding V3 (decisão final)" in result.text
    assert "fact_mismatch" in result.text
    payload = json.loads(log.path.read_text())
    assert payload["grounding"]["status"] == "supported"
    assert payload["grounding_v3"]["reason"] == "fact_mismatch"
    assert payload["answer"] != payload["presented_answer"]
    assert "60 horas" not in payload["presented_answer"]
    response = client.get("/workbench/speech/" + payload["observation_id"])
    assert response.status_code == 200
    assert tts.texts == [payload["presented_answer"]]



@pytest.mark.parametrize("question", [
    "Que dia é hoje?",
    "Que horas são agora?",
    "Que dia é hoje? Que horas são agora?",
])
@pytest.mark.parametrize("mode", ["observe", "enforce"])
def test_admin_clock_response_does_not_show_or_speak_rag_sentinel(
    tmp_path: Path, question: str, mode: str,
) -> None:
    client, log = _client(tmp_path)
    result = client.post(
        "/workbench/run", data={"question": question, "mode": mode, "voice": "cadu"}
    )
    assert result.status_code == 200
    assert "Resposta operacional" in result.text
    assert "NLI não executado" in result.text
    assert "INSUFFICIENT CONTEXT" not in result.text
    row = json.loads(log.path.read_text(encoding="utf-8"))
    assert row["answer_origin"] == "local_clock"
    assert row["grounding_v3"]["reason"] == "local_clock"
    assert row["grounding_v3"]["disposition"] == "allow"
    assert row["grounding"]["score"] is None
    assert row["generation_skipped"]
    assert row["presented_answer"] == row["answer"]
    speech = client.get(f"/workbench/speech/{row['observation_id']}")
    assert speech.status_code == 200
    assert speech.content.startswith(b"RIFF")
