from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from orelhao.config import AudioConfig
from orelhao.interfaces.voice.audio import PCM16Audio
from orelhao.interfaces.voice.devices import native_sample_rate
from orelhao.interfaces.voice.resample import resample_pcm16


class AudioPlayback(Protocol):
    def play(self, audio: PCM16Audio) -> None: ...


@dataclass(slots=True)
class MockAudioPlayback:
    def play(self, audio: PCM16Audio) -> None:
        print(f"[mock playback] {audio.duration_seconds:.2f}s")


class SoundDeviceAudioPlayback:
    def __init__(self, config: AudioConfig) -> None:
        self.config = config

    def play(self, audio: PCM16Audio) -> None:
        if not audio.data:
            return
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError(
                "Suporte de áudio não instalado. Execute: pip install -e '.[audio]'"
            ) from exc

        hardware_rate = native_sample_rate(sd, self.config.output_device, "output")
        playback_audio = resample_pcm16(audio, hardware_rate)
        with sd.RawOutputStream(
            samplerate=hardware_rate,
            device=self.config.output_device,
            channels=playback_audio.channels,
            dtype="int16",
        ) as stream:
            stream.write(playback_audio.data)
