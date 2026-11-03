"""Cache persistente de voz: reuso, invalidação e recuperação."""
from pathlib import Path

import pytest

from orelhao.config import TTSConfig
from orelhao.hardware.voice_prompts import PROMPTS, VoicePromptCache
from orelhao.interfaces.voice.audio import PCM16Audio


class FakeTTS:
    def __init__(self, config: TTSConfig) -> None:
        self.config = config
        self.calls: list[str] = []

    def synthesize(self, text: str) -> PCM16Audio:
        self.calls.append(text)
        return PCM16Audio(data=bytes(4_410), sample_rate=22_050)


def test_audio_is_reused_from_disk_and_speed_invalidation(tmp_path: Path) -> None:
    model = tmp_path / "test.onnx"
    model.write_bytes(b"model")
    tts = FakeTTS(TTSConfig(model=str(model), length_scale=0.88))
    cache = VoicePromptCache(tts, cache_dir=tmp_path / "cache")

    one = cache.audio("greeting")
    two = VoicePromptCache(tts, cache_dir=tmp_path / "cache").audio("greeting")
    assert one == two
    assert tts.calls == [PROMPTS["greeting"]]
    assert cache.root is not None
    assert (cache.root / "greeting.wav").exists()

    faster = FakeTTS(TTSConfig(model=str(model), length_scale=1.0))
    other = VoicePromptCache(faster, cache_dir=tmp_path / "cache")
    assert other.root != cache.root
    other.audio("greeting")
    assert faster.calls == [PROMPTS["greeting"]]


def test_corrupted_audio_is_repaired(tmp_path: Path) -> None:
    tts = FakeTTS(TTSConfig(length_scale=0.88))
    cache = VoicePromptCache(tts, cache_dir=tmp_path)
    cache.audio("waiting")
    assert cache.root is not None
    target = cache.root / "waiting.wav"
    target.write_bytes(b"not-wav")
    assert cache.audio("waiting").data == bytes(4_410)
    assert tts.calls == [PROMPTS["waiting"], PROMPTS["waiting"]]


def test_unknown_prompt_rejected(tmp_path: Path) -> None:
    tts = FakeTTS(TTSConfig())
    cache = VoicePromptCache(tts, cache_dir=tmp_path)
    with pytest.raises(KeyError):
        cache.audio("unknown")
