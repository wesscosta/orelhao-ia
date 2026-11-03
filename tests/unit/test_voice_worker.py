"""Voice worker must speak only the V3 presented text."""
from types import SimpleNamespace

from orelhao.hardware import voice_worker


def test_voice_worker_uses_enforced_answer(monkeypatch) -> None:
    played: list[str] = []
    seen_modes: list[str] = []

    class Capture:
        last_diagnostics = None
        calls = 0

        def capture(self):
            self.calls += 1
            return SimpleNamespace(data=b"" if self.calls == 1 else b"voice")

    class STT:
        def __init__(self, config):
            pass

        def transcribe(self, audio):
            return SimpleNamespace(text="Qual é o horário?")

    class TTS:
        def __init__(self, config):
            pass

        def synthesize(self, text):
            return text

    class Playback:
        def __init__(self, config):
            pass

        def play(self, audio):
            played.append(audio)

    class Workbench:
        def observe(self, question, *, mode):
            seen_modes.append(mode)
            return SimpleNamespace(presented_answer="Resposta validada", answer_origin="rag")

    monkeypatch.setattr(voice_worker, "ensure_audio_ready", lambda: True)
    cfg = SimpleNamespace(
        audio=object(), stt=object(), tts=object(), llm=object()
    )
    monkeypatch.setattr(voice_worker, "load_config", lambda path: cfg)
    monkeypatch.setattr(voice_worker, "resolve_project_path", lambda path: path)
    monkeypatch.setattr(voice_worker, "build_audio_capture", lambda config: Capture())
    monkeypatch.setattr(voice_worker, "FasterWhisperSTTService", STT)
    monkeypatch.setattr(voice_worker, "PiperTTSService", TTS)
    monkeypatch.setattr(voice_worker, "SoundDeviceAudioPlayback", Playback)
    monkeypatch.setattr(voice_worker, "LocalOpenAICompatibleLLMService", lambda cfg: object())
    monkeypatch.setattr(voice_worker, "LocalLLMAnswerGenerator", lambda llm: object())
    monkeypatch.setattr(voice_worker, "default_knowledge_paths", lambda: SimpleNamespace(index="/tmp"))
    monkeypatch.setattr(voice_worker, "build_default_observation_workbench", lambda index, answer_generator, log_path=None: Workbench())
    # Uma captura silenciosa não consome o orçamento de perguntas válidas.
    voice_worker.run_call(max_seconds=100, max_turns=1)
    assert seen_modes == ["enforce"]
    assert played == [
        "Olá, sou o Lumi. Pode falar.",
        "Não ouvi sua voz. Tente novamente.",
        "Resposta validada",
        "Até logo!",
    ]



def test_empty_transcription_warns_once_without_generating_answer(monkeypatch) -> None:
    from types import SimpleNamespace

    played: list[str] = []
    called: list[str] = []

    class Capture:
        last_diagnostics = None
        def capture(self):
            return SimpleNamespace(data=b"noise")

    class STT:
        def __init__(self, config):
            pass
        def transcribe(self, audio):
            return SimpleNamespace(text="")

    class TTS:
        def __init__(self, config):
            pass
        def synthesize(self, text):
            return text

    class Playback:
        def __init__(self, config):
            pass
        def play(self, audio):
            played.append(audio)

    class Workbench:
        def observe(self, question, *, mode):
            called.append(question)
            raise AssertionError("No LLM call for empty STT")

    cfg = SimpleNamespace(audio=object(), stt=object(), tts=object(), llm=object())
    monkeypatch.setattr(voice_worker, "ensure_audio_ready", lambda: True)
    monkeypatch.setattr(voice_worker, "load_config", lambda path: cfg)
    monkeypatch.setattr(voice_worker, "resolve_project_path", lambda path: path)
    monkeypatch.setattr(voice_worker, "build_audio_capture", lambda config: Capture())
    monkeypatch.setattr(voice_worker, "FasterWhisperSTTService", STT)
    monkeypatch.setattr(voice_worker, "PiperTTSService", TTS)
    monkeypatch.setattr(voice_worker, "SoundDeviceAudioPlayback", Playback)
    monkeypatch.setattr(voice_worker, "LocalOpenAICompatibleLLMService", lambda cfg: object())
    monkeypatch.setattr(voice_worker, "LocalLLMAnswerGenerator", lambda llm: object())
    monkeypatch.setattr(voice_worker, "default_knowledge_paths", lambda: SimpleNamespace(index="/tmp"))
    monkeypatch.setattr(
        voice_worker, "build_default_observation_workbench",
        lambda index, answer_generator, log_path=None: Workbench(),
    )
    voice_worker.run_call(max_turns=3)
    assert not called
    assert played == [
        "Olá, sou o Lumi. Pode falar.",
        "Não entendi. Pode repetir?",
        "Até logo!",
    ]
