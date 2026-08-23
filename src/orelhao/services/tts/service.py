from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Protocol

from orelhao.config import TTSConfig
from orelhao.interfaces.voice.audio import PCM16Audio
from orelhao.runtime_paths import resolve_project_path


@dataclass(frozen=True, slots=True)
class SynthesisResult:
    audio: PCM16Audio
    elapsed_seconds: float
    audio_seconds: float
    real_time_factor: float


class TTSService(Protocol):
    def synthesize(self, text: str) -> PCM16Audio: ...


class MockTTSService:
    def synthesize(self, text: str) -> PCM16Audio:
        del text
        return PCM16Audio(data=b"\x00\x00" * 4000, sample_rate=16_000, channels=1)


class PiperTTSService:
    """TTS local via Piper CLI, isolado atrás do contrato TTSService.

    O binário e os pesos são provisionados na appliance; nenhuma chamada de rede
    ocorre durante a síntese. O WAV produzido pelo Piper é normalizado pela
    abstração PCM16Audio antes de seguir ao Audio Engine.
    """

    def __init__(self, config: TTSConfig) -> None:
        self.config = config

    def validate(self) -> None:
        if shutil.which(self.config.executable) is None:
            raise RuntimeError(f"Piper não encontrado no PATH: {self.config.executable!r}")
        model = resolve_project_path(self.config.model)
        config = resolve_project_path(self.config.config) if self.config.config else None
        if not model.is_file():
            raise RuntimeError(
                f"Modelo TTS não encontrado: {model}. Execute: orelhao --tts-provision"
            )
        if config is not None and not config.is_file():
            raise RuntimeError(f"Config do modelo TTS não encontrado: {config}")

    def synthesize_result(self, text: str) -> SynthesisResult:
        clean = text.strip()
        if not clean:
            raise ValueError("Texto para TTS não pode ser vazio")
        self.validate()
        with tempfile.TemporaryDirectory(prefix="orelhao-tts-") as tmp:
            wav = Path(tmp) / "speech.wav"
            model = resolve_project_path(self.config.model)
            model_config = resolve_project_path(self.config.config) if self.config.config else None
            cmd = [self.config.executable, "--model", str(model), "--output_file", str(wav)]
            if model_config is not None:
                cmd += ["--config", str(model_config)]
            if self.config.speaker is not None:
                cmd += ["--speaker", str(self.config.speaker)]
            cmd += [
                "--length_scale",
                str(self.config.length_scale),
                "--noise_scale",
                str(self.config.noise_scale),
                "--noise_w",
                str(self.config.noise_w),
            ]
            started = perf_counter()

            proc = subprocess.run(
                cmd,
                input=clean + "\n",
                text=True,
                capture_output=True,
            )

            elapsed = perf_counter() - started

            if proc.returncode != 0:
                detail = (proc.stderr or proc.stdout).strip()
                raise RuntimeError(f"Falha no Piper TTS: {detail or 'erro desconhecido'}")

            audio = PCM16Audio.from_wav_bytes(wav.read_bytes())

            duration = audio.duration_seconds
            rtf = elapsed / duration if duration > 0 else float("inf")

            return SynthesisResult(
                audio,
                elapsed,
                duration,
                rtf,
            )

    def synthesize(self, text: str) -> PCM16Audio:
        return self.synthesize_result(text).audio
