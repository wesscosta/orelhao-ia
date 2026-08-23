from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from orelhao.config import AudioConfig
from orelhao.interfaces.voice.audio import PCM16Audio
from orelhao.interfaces.voice.devices import native_sample_rate, resolve_device
from orelhao.interfaces.voice.resample import resample_pcm16


class AudioPlayback(Protocol):
    def play(self, audio: PCM16Audio) -> None: ...


@dataclass(slots=True)
class MockAudioPlayback:
    def play(self, audio: PCM16Audio) -> None:
        print(f"[mock playback] {audio.duration_seconds:.2f}s")


class SoundDeviceAudioPlayback:
    """Stable playback facade for the voice appliance.

    The preferred backend delegates WAV playback to a separate PipeWire/ALSA
    process. Besides preserving the WAV sample rate, process isolation prevents a
    PortAudio/native crash from corrupting the long-running Orelhão process.

    ``sounddevice`` remains available as an explicit fallback/backend for
    diagnostics and systems without pw-play/aplay.
    """

    def __init__(self, config: AudioConfig) -> None:
        self.config = config

    def play(self, audio: PCM16Audio) -> None:
        if not audio.data:
            return

        backend = self.config.playback_backend.strip().lower()
        if backend not in {"system", "auto", "sounddevice"}:
            raise RuntimeError(
                f"Backend de playback inválido: {self.config.playback_backend!r}. "
                "Use system, auto ou sounddevice."
            )

        if backend in {"system", "auto"}:
            player = self._resolve_system_player()
            if player is not None:
                self._play_with_system_player(audio, player)
                return
            if backend == "system":
                raise RuntimeError(
                    "Nenhum player de áudio do sistema encontrado. "
                    "Instale PipeWire (pw-play) ou alsa-utils (aplay), ou configure "
                    "audio.playback_backend: sounddevice."
                )

        self._play_with_sounddevice(audio)

    def _resolve_system_player(self) -> str | None:
        configured = self.config.system_player.strip() if self.config.system_player else "auto"
        if configured and configured.lower() != "auto":
            return shutil.which(configured)
        for candidate in ("pw-play", "aplay"):
            executable = shutil.which(candidate)
            if executable:
                return executable
        return None

    @staticmethod
    def _play_with_system_player(audio: PCM16Audio, executable: str) -> None:
        with tempfile.TemporaryDirectory(prefix="orelhao-playback-") as tmp:
            wav_path = Path(tmp) / "speech.wav"
            wav_path.write_bytes(audio.to_wav_bytes())
            name = Path(executable).name
            cmd = [executable, str(wav_path)]
            if name == "aplay":
                cmd = [executable, "-q", str(wav_path)]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                detail = (proc.stderr or proc.stdout).strip()
                raise RuntimeError(
                    f"Falha no playback via {name}: {detail or 'erro desconhecido'}"
                )

    def _play_with_sounddevice(self, audio: PCM16Audio) -> None:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError(
                "Suporte de áudio não instalado. Execute: pip install -e '.[audio]'"
            ) from exc

        resolved_device = resolve_device(sd, self.config.output_device, "output")
        hardware_rate = native_sample_rate(sd, resolved_device, "output")
        playback_audio = resample_pcm16(audio, hardware_rate)
        with sd.RawOutputStream(
            samplerate=hardware_rate,
            device=resolved_device,
            channels=playback_audio.channels,
            dtype="int16",
        ) as stream:
            stream.write(playback_audio.data)
