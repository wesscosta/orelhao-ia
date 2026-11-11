"""O motor residente prepara enquanto o Lumi executa a saudação."""
from __future__ import annotations

import threading
from types import SimpleNamespace

from orelhao.config import TTSConfig
from orelhao.hardware import voice_worker
from orelhao.hardware.voice_prompts import VoicePromptCache


def test_resident_warms_before_first_capture(monkeypatch):
    ready = threading.Event()
    calls: list[str] = []

    class Capture:
        last_diagnostics = None

        def capture(self):
            assert ready.is_set(), "motor residente ainda não preparado"
            calls.append("capture")
            return SimpleNamespace(data=b"")

    class TTS:
        def __init__(self, config):
            self.config = config

        def prepare(self):
            calls.append("prepare")
            ready.set()
            return 0.05

        def synthesize(self, text):
            return text

    class Player:
        def __init__(self, config):
            pass

        def play(self, audio):
            calls.append("play")

    cfg = SimpleNamespace(
        audio=object(), stt=object(),
        tts=SimpleNamespace(engine="resident"),
        llm=object(),
    )
    monkeypatch.setattr(voice_worker, "load_config", lambda _: cfg)
    monkeypatch.setattr(voice_worker, "resolve_project_path", lambda path: path)
    monkeypatch.setattr(voice_worker, "ensure_audio_ready", lambda: True)
    monkeypatch.setattr(voice_worker, "build_audio_capture", lambda _: Capture())
    monkeypatch.setattr(voice_worker, "PiperResidentTTSService", TTS)
    monkeypatch.setattr(voice_worker, "FasterWhisperSTTService", lambda _: object())
    monkeypatch.setattr(voice_worker, "SoundDeviceAudioPlayback", Player)
    monkeypatch.setattr(voice_worker, "LocalOpenAICompatibleLLMService", lambda _: object())
    monkeypatch.setattr(voice_worker, "LocalLLMAnswerGenerator", lambda _: object())
    monkeypatch.setattr(
        voice_worker, "default_knowledge_paths", lambda: SimpleNamespace(index="/tmp")
    )
    monkeypatch.setattr(
        voice_worker, "build_default_observation_workbench",
        lambda index, answer_generator, log_path=None: object(),
    )
    voice_worker.run_call(max_turns=1)
    assert calls.count("prepare") == 1
    assert calls.index("prepare") < calls.index("capture")


def test_static_prompt_cache_is_independent_of_engine(tmp_path):
    def fake(engine):
        return SimpleNamespace(config=TTSConfig(
            engine=engine, model=str(tmp_path / "voice.onnx")
        ))
    cli = VoicePromptCache(fake("cli"), cache_dir=tmp_path)
    resident = VoicePromptCache(fake("resident"), cache_dir=tmp_path)
    assert cli.root == resident.root
