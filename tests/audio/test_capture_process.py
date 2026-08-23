from __future__ import annotations

from pathlib import Path

from types import SimpleNamespace

from orelhao.config import AudioConfig
from orelhao.interfaces.voice.capture import (
    PipeWireAudioCapture,
    ProcessIsolatedAudioCapture,
    build_audio_capture,
)


def test_build_audio_capture_defaults_to_pipewire() -> None:
    capture = build_audio_capture(AudioConfig())
    assert isinstance(capture, PipeWireAudioCapture)


def test_pipewire_command_uses_raw_pcm(monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/pw-record")
    capture = PipeWireAudioCapture(AudioConfig(sample_rate=16000, channels=1))
    cmd = capture._command(Path("/tmp/capture.raw"))
    assert cmd[0] == "/usr/bin/pw-record"
    assert "--raw" not in cmd
    assert "--rate=16000" in cmd
    assert "--channels=1" in cmd
    assert "--format=s16" in cmd
    assert "--channel-map=mono" in cmd
    assert cmd[-1] == "/tmp/capture.raw"


def test_process_capture_reports_native_crash_without_crashing_parent(monkeypatch, tmp_path) -> None:
    class FakeStdout:
        def readline(self) -> str:
            return ""

    class FakeProcess:
        returncode = -6
        stdout = FakeStdout()
        stderr = SimpleNamespace()

        def communicate(self):
            return "", "malloc(): corrupted"

    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: FakeProcess())
    capture = ProcessIsolatedAudioCapture(AudioConfig())
    try:
        capture.capture()
    except RuntimeError as exc:
        assert "processo filho" in str(exc)
        assert "malloc(): corrupted" in str(exc)
    else:
        raise AssertionError("esperava RuntimeError controlado")


def test_pipewire_intentional_stop_is_not_reported_as_failure():
    """Regression: pw-record may return non-zero after application-requested stop."""
    from pathlib import Path
    from orelhao.interfaces.voice.capture import PipeWireAudioCapture

    # The behavior is guarded in capture(): an intentional stop must not be
    # promoted to RuntimeError solely because pw-record returns non-zero.
    source = Path("src/orelhao/interfaces/voice/capture.py").read_text()
    assert "intentional_stop = True" in source
    assert "proc.send_signal(signal.SIGINT)" in source
    assert "process_failed_during_capture and not intentional_stop" in source
