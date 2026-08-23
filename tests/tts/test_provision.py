from pathlib import Path

from orelhao.config import TTSConfig
from orelhao.services.tts.provision import provision_piper_voice


def test_provision_voice_copies_files(tmp_path: Path, monkeypatch):
    cache = tmp_path / "cache"
    cache.mkdir()
    files = {
        "model.onnx": b"model",
        "model.onnx.json": b"{}",
        "MODEL_CARD": b"card",
    }
    for name, payload in files.items():
        (cache / name).write_bytes(payload)

    def fake_download(repo_id: str, filename: str):
        del repo_id
        return str(cache / Path(filename).name)

    import huggingface_hub
    monkeypatch.setattr(huggingface_hub, "hf_hub_download", fake_download)

    model = tmp_path / "models" / "voice.onnx"
    config = tmp_path / "models" / "voice.onnx.json"
    cfg = TTSConfig(
        model=str(model), config=str(config),
        voice_model_file="x/model.onnx",
        voice_config_file="x/model.onnx.json",
        voice_model_card_file="x/MODEL_CARD",
    )
    result = provision_piper_voice(cfg)
    assert result.model.read_bytes() == b"model"
    assert result.config.read_bytes() == b"{}"
    assert result.model_card.read_bytes() == b"card"
