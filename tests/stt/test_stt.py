from array import array

import pytest

from orelhao.config import STTConfig
from orelhao.interfaces.voice.audio import PCM16Audio
from orelhao.services.stt.service import FasterWhisperSTTService, MockSTTService, TranscriptionResult


def test_mock_stt_returns_structured_result() -> None:
    audio = PCM16Audio(data=b"\x00\x00" * 16_000)
    result = MockSTTService().transcribe(audio)
    assert result.text
    assert result.language == "pt"
    assert result.audio_seconds == pytest.approx(1.0)


def test_real_time_factor() -> None:
    result = TranscriptionResult(text="ok", audio_seconds=2.0, elapsed_seconds=0.5)
    assert result.real_time_factor == pytest.approx(0.25)


def test_pcm_conversion_normalizes_int16() -> None:
    audio = PCM16Audio(data=array("h", [0, 16384, -16384]).tobytes())
    waveform = FasterWhisperSTTService._pcm16_to_float32(audio)
    assert waveform.tolist() == pytest.approx([0.0, 0.5, -0.5])


def test_stt_config_defaults() -> None:
    config = STTConfig()
    assert config.language == "pt"
    assert config.model == "small"


def test_stt_cpu_fallback_defaults_enabled() -> None:
    config = STTConfig()
    assert config.fallback_to_cpu is True
    assert config.cpu_fallback_compute_type == "int8"
