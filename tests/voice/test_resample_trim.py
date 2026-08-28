import numpy as np

from orelhao.interfaces.voice.audio import PCM16Audio
from orelhao.interfaces.voice.resample import trim_silence_pcm16


def test_trim_silence_keeps_speech_with_padding() -> None:
    silence = np.zeros(16_000, dtype=np.int16)
    speech = np.full(8_000, 4_000, dtype=np.int16)
    audio = PCM16Audio(np.concatenate((silence, speech, silence)).tobytes())

    trimmed = trim_silence_pcm16(audio)

    assert 0.8 <= trimmed.duration_seconds <= 1.0


def test_trim_silence_returns_empty_when_no_speech() -> None:
    audio = PCM16Audio(np.zeros(16_000, dtype=np.int16).tobytes())

    assert trim_silence_pcm16(audio).data == b""
