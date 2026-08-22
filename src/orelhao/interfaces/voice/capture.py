from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Protocol

from orelhao.config import AudioConfig
from orelhao.interfaces.voice.audio import PCM16Audio
from orelhao.interfaces.voice.devices import native_sample_rate
from orelhao.interfaces.voice.resample import resample_pcm16
from orelhao.interfaces.voice.vad import AdaptiveEnergyVAD, EnergyVAD


class AudioCapture(Protocol):
    def capture(self) -> PCM16Audio: ...


@dataclass(frozen=True, slots=True)
class CaptureDiagnostics:
    hardware_rate: int
    pipeline_rate: int
    noise_floor: float
    speech_threshold: float
    speech_detected: bool
    stop_reason: str
    overflow_count: int = 0


@dataclass(slots=True)
class MockAudioCapture:
    sample_rate: int = 16_000

    def capture(self) -> PCM16Audio:
        return PCM16Audio(data=b"\x00\x00" * 1600, sample_rate=self.sample_rate, channels=1)


class SoundDeviceAudioCapture:
    """Captura na taxa nativa, VAD adaptativo e normalização para 16 kHz.

    O tempo máximo de gravação é apenas um failsafe. O encerramento normal ocorre
    após detecção de fala seguida do período de silêncio configurado.
    """

    def __init__(self, config: AudioConfig) -> None:
        self.config = config
        self.last_diagnostics: CaptureDiagnostics | None = None

    def capture(self) -> PCM16Audio:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError(
                "Suporte de áudio não instalado. Execute: pip install -e '.[audio]'"
            ) from exc

        cfg = self.config
        hardware_rate = native_sample_rate(sd, cfg.input_device, "input")
        frames_per_block = max(1, int(hardware_rate * cfg.block_ms / 1000))
        pre_roll_blocks = max(1, cfg.pre_roll_ms // cfg.block_ms)
        silence_blocks_required = max(1, cfg.silence_ms // cfg.block_ms)
        calibration_blocks = max(1, cfg.vad_calibration_ms // cfg.block_ms)
        speech_start_blocks = max(1, int(cfg.speech_start_timeout_seconds * 1000 / cfg.block_ms))
        max_blocks = max(1, int(cfg.max_record_seconds * 1000 / cfg.block_ms))

        adaptive_vad = AdaptiveEnergyVAD(
            threshold_multiplier=cfg.vad_threshold_multiplier,
            min_threshold=cfg.vad_min_threshold,
            max_threshold=cfg.vad_max_threshold,
        )
        fixed_vad = EnergyVAD(cfg.rms_threshold)

        calibration: list[bytes] = []
        pre_roll: deque[bytes] = deque(maxlen=pre_roll_blocks)
        recorded: list[bytes] = []
        speech_started = False
        silence_blocks = 0
        blocks_waiting_for_speech = 0
        overflow_count = 0
        stop_reason = "max_duration"

        try:
            stream_context = sd.RawInputStream(
                samplerate=hardware_rate,
                blocksize=frames_per_block,
                device=cfg.input_device,
                channels=cfg.channels,
                dtype="int16",
            )
        except Exception as exc:
            raise RuntimeError(
                f"Não foi possível abrir a entrada de áudio {cfg.input_device!r} "
                f"em {hardware_rate} Hz: {exc}"
            ) from exc

        with stream_context as stream:
            # Calibração ocorre antes de aguardar a fala. O usuário deve ficar em
            # silêncio por uma fração de segundo, conforme mensagem da CLI.
            for _ in range(calibration_blocks):
                raw, overflowed = stream.read(frames_per_block)
                if overflowed:
                    overflow_count += 1
                calibration.append(bytes(raw))

            if cfg.adaptive_vad:
                threshold = adaptive_vad.calibrate(calibration)
                vad = adaptive_vad
                noise_floor = adaptive_vad.noise_floor
            else:
                threshold = fixed_vad.rms_threshold
                vad = fixed_vad
                noise_floor = 0.0

            for _ in range(max_blocks):
                raw, overflowed = stream.read(frames_per_block)
                if overflowed:
                    overflow_count += 1
                block = bytes(raw)

                if not speech_started:
                    blocks_waiting_for_speech += 1
                    pre_roll.append(block)
                    if vad.is_speech(block):
                        speech_started = True
                        recorded.extend(pre_roll)
                        pre_roll.clear()
                        continue
                    if blocks_waiting_for_speech >= speech_start_blocks:
                        stop_reason = "speech_start_timeout"
                        break
                    continue

                recorded.append(block)
                if vad.is_speech(block):
                    silence_blocks = 0
                else:
                    silence_blocks += 1
                    if silence_blocks >= silence_blocks_required:
                        stop_reason = "silence"
                        break

        self.last_diagnostics = CaptureDiagnostics(
            hardware_rate=hardware_rate,
            pipeline_rate=cfg.sample_rate,
            noise_floor=noise_floor,
            speech_threshold=threshold,
            speech_detected=speech_started,
            stop_reason=stop_reason,
            overflow_count=overflow_count,
        )

        if not speech_started:
            return PCM16Audio(data=b"", sample_rate=cfg.sample_rate, channels=cfg.channels)

        native_audio = PCM16Audio(
            data=b"".join(recorded),
            sample_rate=hardware_rate,
            channels=cfg.channels,
        )
        return resample_pcm16(native_audio, cfg.sample_rate)
