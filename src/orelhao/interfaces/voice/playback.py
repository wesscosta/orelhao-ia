from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from orelhao.config import AudioConfig
from orelhao.interfaces.voice.audio import PCM16Audio


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

        with sd.RawOutputStream(
            samplerate=audio.sample_rate,
            device=self.config.output_device,
            channels=audio.channels,
            dtype="int16",
        ) as stream:
            stream.write(audio.data)
