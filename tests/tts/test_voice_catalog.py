from __future__ import annotations

import pytest

from orelhao.config import TTSConfig
from orelhao.services.tts import voice_catalog
from orelhao.services.tts.voice_catalog import (
    WorkbenchPiperVoices,
    validate_voice_id,
    voice_options,
)


def test_closed_catalog_and_friendly_labels() -> None:
    options = voice_options()
    assert [(x.id, x.label) for x in options] == [
        ("cadu", "Piper Cadu (original)"),
        ("faber", "Piper Faber (experimental)"),
    ]
    for bad in ("", "../etc/passwd", "Cadu", "kokoro", "/tmp/voice.onnx"):
        with pytest.raises(ValueError, match="Voz inválida"):
            validate_voice_id(bad)


def test_lazy_piper_factory_uses_fixed_paths_and_separate_instances(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[TTSConfig] = []

    class FakePiper:
        def __init__(self, config: TTSConfig) -> None:
            seen.append(config)

    monkeypatch.setattr(voice_catalog, "PiperTTSService", FakePiper)
    catalog = WorkbenchPiperVoices(TTSConfig())
    cadu = catalog.get("cadu")
    faber = catalog.get("faber")
    assert catalog.get("cadu") is cadu
    assert catalog.get("faber") is faber
    assert len(seen) == 2
    assert seen[0].model == "models/tts/pt_BR-cadu-medium.onnx"
    assert seen[1].model == "models/tts/pt_BR-faber-medium.onnx"
    assert seen[0].config == seen[0].model + ".json"
    assert seen[1].config == seen[1].model + ".json"
