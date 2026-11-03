"""Silêncio normal, pausa solicitada e retorno ao diálogo pelo monofone."""
from __future__ import annotations

from collections import deque
from types import SimpleNamespace

from orelhao.hardware import voice_worker
from orelhao.hardware.idle_policy import CallIdlePolicy
from orelhao.hardware.voice_prompts import PROMPTS


def test_silencio_normal_avisa_uma_vez_e_encerra() -> None:
    policy = CallIdlePolicy()
    assert policy.on_missing_speech() == "prompt"
    assert policy.on_missing_speech() == "close"


def test_pausa_solicitada_aguarda_mais_e_nao_repete_aviso() -> None:
    policy = CallIdlePolicy()
    policy.on_phrase(requested_pause=True)
    assert policy.paused
    assert [policy.on_missing_speech() for _ in range(4)] == [
        "wait", "wait", "wait", "close",
    ]


def test_retorno_da_pausa_reinicia_contagem_de_silencio() -> None:
    policy = CallIdlePolicy()
    policy.on_phrase(requested_pause=True)
    assert policy.on_missing_speech() == "wait"
    assert policy.on_missing_speech() == "wait"
    policy.on_phrase(requested_pause=False)
    assert not policy.paused
    assert policy.consecutive_silences == 0
    assert policy.on_missing_speech() == "prompt"
    assert policy.on_missing_speech() == "close"


def _run_scenario(monkeypatch, utterances: list[str | None]) -> tuple[list[str], int]:
    played: list[str] = []
    data = deque(utterances)
    state = {"capture_calls": 0}

    class Capture:
        last_diagnostics = None

        def capture(self):
            state["capture_calls"] += 1
            if not data:
                raise AssertionError("A chamada ultrapassou o encerramento esperado")
            utterance = data.popleft()
            if utterance is None:
                return SimpleNamespace(data=b"")
            return SimpleNamespace(data=utterance.encode("utf-8"))

    class STT:
        def __init__(self, _config):
            pass

        def transcribe(self, audio):
            return SimpleNamespace(text=audio.data.decode("utf-8"))

    class TTS:
        def __init__(self, _config):
            pass

        def synthesize(self, text):
            return text

    class Playback:
        def __init__(self, _config):
            pass

        def play(self, audio):
            played.append(audio)

    class Workbench:
        def observe(self, question, *, mode):
            raise AssertionError(f"Não deve chamar o RAG: {question}")

    monkeypatch.setattr(voice_worker, "ensure_audio_ready", lambda: True)
    monkeypatch.setattr(
        voice_worker, "load_config",
        lambda _path: SimpleNamespace(audio=None, stt=None, tts=None, llm=None),
    )
    monkeypatch.setattr(voice_worker, "resolve_project_path", lambda path: path)
    monkeypatch.setattr(voice_worker, "build_audio_capture", lambda _cfg: Capture())
    monkeypatch.setattr(voice_worker, "FasterWhisperSTTService", STT)
    monkeypatch.setattr(voice_worker, "PiperTTSService", TTS)
    monkeypatch.setattr(voice_worker, "SoundDeviceAudioPlayback", Playback)
    monkeypatch.setattr(voice_worker, "LocalOpenAICompatibleLLMService", lambda _cfg: object())
    monkeypatch.setattr(voice_worker, "LocalLLMAnswerGenerator", lambda _llm: object())
    monkeypatch.setattr(
        voice_worker, "default_knowledge_paths",
        lambda: SimpleNamespace(index="/tmp"),
    )
    monkeypatch.setattr(
        voice_worker, "build_default_observation_workbench",
        lambda *_args, **_kwargs: Workbench(),
    )
    voice_worker.run_call(max_seconds=180, max_turns=12)
    assert not data
    return played, state["capture_calls"]


def test_silencio_encerra_sem_esperar_12_turnos(monkeypatch) -> None:
    played, captures = _run_scenario(monkeypatch, [None, None])
    assert captures == 2
    assert played == [
        PROMPTS["greeting"],
        PROMPTS["idle_check"],
        PROMPTS["closing_inactivity"],
    ]


def test_pausa_solicitada_nao_repete_aviso_e_encerra(monkeypatch) -> None:
    played, captures = _run_scenario(
        monkeypatch, ["Só um instante", None, None, None, None]
    )
    assert captures == 5
    assert played == [
        PROMPTS["greeting"],
        PROMPTS["ack_wait"],
        PROMPTS["closing_inactivity"],
    ]


def test_fala_retorna_da_pausa_e_zera_inatividade(monkeypatch) -> None:
    played, captures = _run_scenario(
        monkeypatch,
        ["Só um instante", None, None, "Quais os cursos do Senac?", None, None],
    )
    assert captures == 6
    assert played == [
        PROMPTS["greeting"],
        PROMPTS["ack_wait"],
        PROMPTS["courses_overview"],
        PROMPTS["idle_check"],
        PROMPTS["closing_inactivity"],
    ]


def test_stt_rejeitado_segue_politica_de_inatividade(monkeypatch) -> None:
    played, captures = _run_scenario(
        monkeypatch,
        ["Transcrição e Legendas por Paulo Montenegro", None],
    )
    assert captures == 2
    assert played == [
        PROMPTS["greeting"],
        PROMPTS["no_transcription"],
        PROMPTS["closing_inactivity"],
    ]

def test_programming_menu_do_monofone_sem_rag(monkeypatch) -> None:
    played, captures = _run_scenario(
        monkeypatch,
        [
            "Quais os cursos no Senac?",
            "Área de Informática.",
            "Programação.",
            "Em Teresina.",
            "Finaliza.",
        ],
    )
    assert captures == 5
    assert played == [
        PROMPTS["greeting"],
        PROMPTS["courses_overview"],
        PROMPTS["technology_area"],
        PROMPTS["programming_area"],
        PROMPTS["programming_teresina"],
        PROMPTS["closing"],
    ]
