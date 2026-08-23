from pathlib import Path

import pytest

from orelhao.config import TTSConfig
from orelhao.services.tts.service import MockTTSService, PiperTTSService


def test_tts_config_defaults():
    cfg = TTSConfig()
    assert cfg.backend == "piper"
    assert cfg.executable == "piper"


def test_mock_tts_returns_audio():
    audio = MockTTSService().synthesize("Olá")
    assert audio.sample_rate == 16000
    assert audio.duration_seconds > 0


def test_piper_rejects_empty_text():
    service = PiperTTSService(TTSConfig())
    with pytest.raises(ValueError):
        service.synthesize_result("   ")


def test_piper_validate_reports_missing_model(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/piper")
    service = PiperTTSService(TTSConfig(model=str(tmp_path / "missing.onnx")))
    with pytest.raises(RuntimeError, match="Modelo TTS não encontrado"):
        service.validate()
