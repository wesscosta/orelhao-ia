"""Regressão do Piper residente com dublê, independente do modelo grande."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from orelhao.config import TTSConfig
from orelhao.services.tts.resident import PiperResidentTTSService


def test_resident_loads_once_and_emits_pcm16_without_temp_files(tmp_path, monkeypatch):
    model = tmp_path / "voice.onnx"
    model.write_bytes(b"model-placeholder")
    config = tmp_path / "voice.onnx.json"
    config.write_text("{}", encoding="utf-8")
    calls = {"loads": 0, "syntheses": 0, "config": None}

    class FakeVoice:
        def synthesize(self, text, syn_config):
            calls["syntheses"] += 1
            calls["config"] = syn_config
            assert text
            yield SimpleNamespace(
                sample_width=2, sample_channels=1, sample_rate=22_050,
                audio_int16_bytes=b"\x01\x00" * 2205,
            )

    def load(*_args, **_kwargs):
        calls["loads"] += 1
        return FakeVoice()

    monkeypatch.setattr("piper.voice.PiperVoice.load", load)
    service = PiperResidentTTSService(TTSConfig(
        model=str(model), config=str(config), speaker=0, length_scale=0.88
    ))
    assert service.prepare() >= 0
    first = service.synthesize_result("Senac Piauí")
    second = service.synthesize_result("Olá")
    assert calls["loads"] == 1
    assert calls["syntheses"] == 2
    assert calls["config"].speaker_id == 0
    assert calls["config"].length_scale == 0.88
    assert first.audio.sample_rate == 22_050
    assert first.audio.duration_seconds == pytest.approx(0.1)
    assert second.elapsed_seconds >= 0
    assert set(tmp_path.iterdir()) == {model, config}


def test_resident_rejects_empty_text():
    with pytest.raises(ValueError, match="vazio"):
        PiperResidentTTSService(TTSConfig()).synthesize(" \n ")
