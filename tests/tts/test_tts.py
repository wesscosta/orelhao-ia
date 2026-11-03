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



def test_piper_finds_executable_inside_active_python_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from orelhao.services.tts import service as tts_module

    executable = tmp_path / "piper"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    monkeypatch.setattr(tts_module.shutil, "which", lambda _: None)
    monkeypatch.setattr(tts_module.sys, "executable", str(tmp_path / "python"))
    assert PiperTTSService(TTSConfig())._executable() == str(executable)
