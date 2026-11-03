"""Regressões reais da conversa por monofone: menu, ruído, encerramento."""
from types import SimpleNamespace

from orelhao.hardware import voice_worker
from orelhao.hardware.voice_intents import (
    VoiceIntentRouter,
    looks_like_stt_hallucination,
)


def test_resposta_ao_menu_de_cursos_e_encerramento() -> None:
    router = VoiceIntentRouter()
    first = router.route("Os Custos Senac.")
    assert first is not None and first.prompt == "courses_or_prices"
    assert router.awaiting_courses_or_prices
    second = router.route("Eu quero saber os cursos.")
    assert second is not None and second.prompt == "courses_overview"
    assert router.awaiting_course_area
    third = router.route("Área... Comercial.")
    assert third is not None and third.prompt == "commerce_area"
    ending = router.route("Finaliza.")
    assert ending is not None and ending.prompt == "closing" and ending.end_session


def test_escolha_de_precos_pede_curso_especifico() -> None:
    router = VoiceIntentRouter()
    router.route("Os Custos Senac")
    reply = router.route("Eu quero saber os preços")
    assert reply is not None and reply.prompt == "ask_specific_course"
    assert not router.awaiting_courses_or_prices


def test_consulta_especifica_ainda_usa_rag() -> None:
    router = VoiceIntentRouter()
    router.route("Os Custos Senac")
    assert router.route("Qual é o preço do Excel Avançado?") is None
    assert router.route("Qual a carga horária do Excel?") is None


def test_variacoes_de_fala_curta_e_encerramento() -> None:
    router = VoiceIntentRouter()
    for phrase in ("Finaliza", "Pode encerrar", "Tchau", "Quero finalizar"):
        result = router.route(phrase)
        assert result is not None and result.end_session, phrase
    assert router.route("Como finalizar a matrícula?") is None
    waiting = router.route("Ah, pois espera só um instante.")
    assert waiting is not None and waiting.prompt == "ack_wait"
    assert looks_like_stt_hallucination("Transcrição e Legendas por Paulo Montenegro")


def test_resposta_invalida_nao_consume_turnos_e_encerra_uma_vez(monkeypatch) -> None:
    outputs: list[str] = []
    spoken = iter((
        "Transcrição e Legendas por Paulo Montenegro",
        "Os Custos Senac.",
        "Eu quero saber os cursos.",
        "Finaliza.",
    ))
    called: list[str] = []

    class Capture:
        last_diagnostics = None
        calls = 0

        def capture(self):
            self.calls += 1
            assert self.calls <= 4, "Uma mensagem de encerramento deve parar o worker."
            return SimpleNamespace(data=b"voice")

    capture = Capture()

    class STT:
        def __init__(self, _cfg):
            pass

        def transcribe(self, _audio):
            return SimpleNamespace(text=next(spoken))

    class TTS:
        def __init__(self, _cfg):
            pass

        def synthesize(self, text):
            return text

    class Playback:
        def __init__(self, _cfg):
            pass

        def play(self, audio):
            outputs.append(audio)

    class Workbench:
        def observe(self, question, *, mode):
            called.append(question)
            raise AssertionError("Menu e encerramento não devem chamar o RAG.")

    monkeypatch.setattr(voice_worker, "ensure_audio_ready", lambda: True)
    monkeypatch.setattr(
        voice_worker, "load_config",
        lambda _path: SimpleNamespace(audio=None, stt=None, tts=None, llm=None),
    )
    monkeypatch.setattr(voice_worker, "resolve_project_path", lambda path: path)
    monkeypatch.setattr(voice_worker, "build_audio_capture", lambda _cfg: capture)
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
    voice_worker.run_call(max_seconds=100, max_turns=3)
    assert capture.calls == 4
    assert called == []
    assert outputs[0] == "Olá, sou o Lumi. Pode falar."
    assert outputs.count("Até logo!") == 1
    assert "Não entendi. Pode repetir?" in outputs
    assert "Você quer saber os cursos ou o preço de algum curso?" in outputs
    assert outputs[-2].startswith("O Senac oferece cursos")
