"""Regressões da rota P3 do Dell: ganho moderado e PipeWire por nome."""
from __future__ import annotations

import runpy
from pathlib import Path
from types import SimpleNamespace

from orelhao.config import AudioConfig, load_config
from orelhao.interfaces.voice.audio import PCM16Audio
from orelhao.interfaces.voice.capture import PipeWireAudioCapture
from orelhao.interfaces.voice.playback import SoundDeviceAudioPlayback


def test_pipewire_target_explicitly_selects_microphone(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("shutil.which", lambda _name: "/usr/bin/pw-record")
    capture = PipeWireAudioCapture(AudioConfig(
        pipewire_target="alsa_input.pci-0000_00_1f.3.analog-stereo",
    ))
    command = capture._command(tmp_path / "capture.raw")
    assert "--target=alsa_input.pci-0000_00_1f.3.analog-stereo" in command
    assert command[-1].endswith("capture.raw")


def test_pipewire_playback_target_explicitly_selects_speaker(monkeypatch) -> None:
    command: list[str] = []
    monkeypatch.setattr("shutil.which", lambda _name: "/usr/bin/pw-play")

    def fake_run(args, check, capture_output, text):
        assert check is False
        del capture_output, text
        command.extend(args)
        assert Path(args[-1]).is_file()
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr("subprocess.run", fake_run)
    SoundDeviceAudioPlayback(AudioConfig(
        playback_backend="system",
        pipewire_playback_target="alsa_output.pci-0000_00_1f.3.analog-stereo",
    )).play(PCM16Audio(
        data=b"\x00\x00" * 160, sample_rate=16000, channels=1,
    ))
    assert command[0] == "/usr/bin/pw-play"
    assert command[1] == "--target=alsa_output.pci-0000_00_1f.3.analog-stereo"


def test_server_profile_pins_both_pipewire_nodes_without_hardcoded_indices() -> None:
    config = load_config("config/orelhao-server.qwen.local.yaml")
    assert config.audio.pipewire_target == "alsa_input.pci-0000_00_1f.3.analog-stereo"
    assert config.audio.pipewire_playback_target == (
        "alsa_output.pci-0000_00_1f.3.analog-stereo"
    )


def test_headset_setup_avoids_broken_wpctl_default_nodes(monkeypatch) -> None:
    class Volume:
        value_flat = 0.35

    class Port:
        def __init__(self, name):
            self.name = name

    class Device:
        def __init__(self, name, port_name):
            self.name = name
            self.index = 48
            self.port_active = Port(port_name)
            self.port_list = [Port(port_name)]
            self.volume = Volume()
            self.mute = 0

    sink = Device("alsa_output.dell", "analog-output-headphones")
    source = Device("alsa_input.dell", "analog-input-headset-mic")

    class Pulse:
        def __init__(self, _name):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def sink_list(self):
            return [sink]

        def source_list(self):
            return [source]

        def sink_port_set(self, _index, name):
            sink.port_active = Port(name)

        def source_port_set(self, _index, name):
            source.port_active = Port(name)

        def sink_mute(self, _index, mute):
            sink.mute = mute

        def source_mute(self, _index, mute):
            source.mute = mute

        def volume_set_all_chans(self, device, level):
            device.volume.value_flat = level

    import pulsectl

    monkeypatch.setattr(pulsectl, "Pulse", Pulse)
    invoked: list[tuple[str, ...]] = []

    def fake_run(args, **kwargs):
        assert kwargs["check"]
        invoked.append(tuple(args))
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr("subprocess.run", fake_run)
    script_path = Path("scripts/configure_headset_audio.py")
    namespace = runpy.run_path(str(script_path))
    namespace["configure"]()
    assert invoked == [
        ("amixer", "-c", "0", "sset", "Capture", "40%", "cap"),
    ]
    assert sink.volume.value_flat == 0.35
    assert source.port_active.name == "analog-input-headset-mic"
