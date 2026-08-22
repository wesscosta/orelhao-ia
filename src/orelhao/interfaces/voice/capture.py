from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Protocol

from orelhao.config import AudioConfig
from orelhao.interfaces.voice.audio import PCM16Audio
from orelhao.interfaces.voice.vad import EnergyVAD


class AudioCapture(Protocol):
    def capture(self) -> PCM16Audio: ...


@dataclass(slots=True)
class MockAudioCapture:
    sample_rate: int = 16_000

    def capture(self) -> PCM16Audio:
        return PCM16Audio(data=b"\x00\x00" * 1600, sample_rate=self.sample_rate, channels=1)


class SoundDeviceAudioCapture:
    """Captura PCM16 e encerra automaticamente após silêncio pós-fala."""

    def __init__(self, config: AudioConfig) -> None:
        self.config = config
        self.vad = EnergyVAD(config.rms_threshold)

    def capture(self) -> PCM16Audio:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError(
                "Suporte de áudio não instalado. Execute: pip install -e '.[audio]'"
            ) from exc

        cfg = self.config
        frames_per_block = max(1, int(cfg.sample_rate * cfg.block_ms / 1000))
        pre_roll_blocks = max(1, cfg.pre_roll_ms // cfg.block_ms)
        silence_blocks_required = max(1, cfg.silence_ms // cfg.block_ms)
        max_blocks = max(1, int(cfg.max_record_seconds * 1000 / cfg.block_ms))

        pre_roll: deque[bytes] = deque(maxlen=pre_roll_blocks)
        recorded: list[bytes] = []
        speech_started = False
        silence_blocks = 0

        with sd.RawInputStream(
            samplerate=cfg.sample_rate,
            blocksize=frames_per_block,
            device=cfg.input_device,
            channels=cfg.channels,
            dtype="int16",
        ) as stream:
            for _ in range(max_blocks):
                raw, overflowed = stream.read(frames_per_block)
                if overflowed:
                    # O overflow não invalida toda a captura; a telemetria tratará isso depois.
                    pass
                block = bytes(raw)

                if not speech_started:
                    pre_roll.append(block)
                    if self.vad.is_speech(block):
                        speech_started = True
                        recorded.extend(pre_roll)
                        pre_roll.clear()
                    continue

                recorded.append(block)
                if self.vad.is_speech(block):
                    silence_blocks = 0
                else:
                    silence_blocks += 1
                    if silence_blocks >= silence_blocks_required:
                        break

        if not speech_started:
            return PCM16Audio(data=b"", sample_rate=cfg.sample_rate, channels=cfg.channels)

        return PCM16Audio(
            data=b"".join(recorded),
            sample_rate=cfg.sample_rate,
            channels=cfg.channels,
        )
