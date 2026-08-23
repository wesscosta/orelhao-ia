from pathlib import Path

from orelhao.runtime_paths import project_root, resolve_project_path


def test_resolve_project_path_is_independent_of_cwd(tmp_path: Path, monkeypatch):
    root = tmp_path / "app"
    monkeypatch.setenv("ORELHAO_ROOT", str(root))
    monkeypatch.chdir(tmp_path)
    assert project_root() == root.resolve()
    assert resolve_project_path("models/tts/voice.onnx") == root.resolve() / "models/tts/voice.onnx"
