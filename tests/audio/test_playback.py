from __future__ import annotations

import wave
from io import BytesIO
from types import SimpleNamespace

from orelhao.config import AudioConfig
from orelhao.interfaces.voice.audio import PCM16Audio
from orelhao.interfaces.voice.playback import SoundDeviceAudioPlayback


def test_system_playback_preserves_wav_sample_rate(monkeypatch):
    captured: dict[str, int] = {}

    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}" if name == "pw-play" else None)

    def fake_run(cmd, capture_output, text):
        del capture_output, text
        payload = open(cmd[-1], "rb").read()
        with wave.open(BytesIO(payload), "rb") as wav:
            captured["rate"] = wav.getframerate()
            captured["frames"] = wav.getnframes()
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr("subprocess.run", fake_run)
    audio = PCM16Audio(data=b"\x00\x00" * 22_050, sample_rate=22_050, channels=1)
    playback = SoundDeviceAudioPlayback(AudioConfig(playback_backend="system"))
    playback.play(audio)

    assert captured["rate"] == 22_050
    assert captured["frames"] == 22_050


def test_system_playback_requires_player(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: None)
    audio = PCM16Audio(data=b"\x00\x00" * 100, sample_rate=22_050, channels=1)
    playback = SoundDeviceAudioPlayback(AudioConfig(playback_backend="system"))

    try:
        playback.play(audio)
    except RuntimeError as exc:
        assert "pw-play" in str(exc)
    else:
        raise AssertionError("Era esperado RuntimeError sem player do sistema")
