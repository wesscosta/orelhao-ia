from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Protocol

from orelhao.config import STTConfig
from orelhao.interfaces.voice.audio import PCM16Audio


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    text: str
    audio_seconds: float
    elapsed_seconds: float
    language: str | None = None
    language_probability: float | None = None
    segments: int = 0

    @property
    def real_time_factor(self) -> float:
        """Tempo de processamento / duração do áudio. Menor que 1 = mais rápido que tempo real."""
        if self.audio_seconds <= 0:
            return 0.0
        return self.elapsed_seconds / self.audio_seconds


class STTService(Protocol):
    def transcribe(self, audio: PCM16Audio) -> TranscriptionResult: ...


class MockSTTService:
    def transcribe(self, audio: PCM16Audio) -> TranscriptionResult:
        return TranscriptionResult(
            text="Quais cursos de tecnologia o Senac oferece?",
            audio_seconds=audio.duration_seconds,
            elapsed_seconds=0.001,
            language="pt",
            language_probability=1.0,
            segments=1,
        )


class FasterWhisperSTTService:
    """STT local usando faster-whisper/CTranslate2.

    O import e o carregamento do modelo são lazy para que o restante da aplicação
    continue executável sem a dependência opcional de STT instalada.
    """

    def __init__(self, config: STTConfig) -> None:
        self.config = config
        self._model: Any | None = None
        self._effective_device = config.device
        self._effective_compute_type = config.compute_type
        self.used_cpu_fallback = False

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model

        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "Backend STT não instalado. Execute: pip install -e '.[audio,stt]'"
            ) from exc

        kwargs: dict[str, Any] = {
            "device": self._effective_device,
            "compute_type": self._effective_compute_type,
        }
        if self.config.cpu_threads > 0:
            kwargs["cpu_threads"] = self.config.cpu_threads
        if self.config.num_workers > 0:
            kwargs["num_workers"] = self.config.num_workers

        self._model = WhisperModel(self.config.model, **kwargs)
        return self._model

    @staticmethod
    def _pcm16_to_float32(audio: PCM16Audio) -> Any:
        if audio.channels != 1:
            raise ValueError("O STT da v0.2 espera áudio mono")
        if audio.sample_rate != 16_000:
            raise ValueError("O STT da v0.2 espera áudio em 16 kHz")

        try:
            import numpy as np
        except ImportError as exc:
            raise RuntimeError("NumPy é necessário para o backend STT") from exc

        # Copy evita buffer somente-leitura e mantém o array independente do objeto PCM.
        samples = np.frombuffer(audio.data, dtype=np.int16).astype(np.float32)
        return samples / 32768.0

    def transcribe(self, audio: PCM16Audio) -> TranscriptionResult:
        if not audio.data:
            return TranscriptionResult(
                text="",
                audio_seconds=0.0,
                elapsed_seconds=0.0,
                language=self.config.language,
                segments=0,
            )

        model = self._load_model()
        waveform = self._pcm16_to_float32(audio)
        started = perf_counter()

        try:
            segments_iter, info = model.transcribe(
                waveform,
                language=self.config.language,
                beam_size=self.config.beam_size,
                vad_filter=False,  # O Audio Engine já executa VAD antes do STT.
                condition_on_previous_text=False,
                temperature=0.0,
                initial_prompt=self.config.initial_prompt,
            )
            segments = list(segments_iter)
        except RuntimeError as exc:
            message = str(exc).lower()
            cuda_runtime_problem = any(token in message for token in ("libcublas", "cuda", "cudnn"))
            if not (self.config.fallback_to_cpu and cuda_runtime_problem and self._effective_device != "cpu"):
                raise

            # Uma instalação pode ter GPU visível mas runtime CUDA incompleto.
            # Nessa situação o atendimento continua em CPU, com telemetria indicando fallback.
            self._effective_device = "cpu"
            self._effective_compute_type = self.config.cpu_fallback_compute_type
            self._model = None
            self.used_cpu_fallback = True
            model = self._load_model()
            segments_iter, info = model.transcribe(
                waveform,
                language=self.config.language,
                beam_size=self.config.beam_size,
                vad_filter=False,
                condition_on_previous_text=False,
                temperature=0.0,
                initial_prompt=self.config.initial_prompt,
            )
            segments = list(segments_iter)
        elapsed = perf_counter() - started
        text = " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()

        return TranscriptionResult(
            text=text,
            audio_seconds=audio.duration_seconds,
            elapsed_seconds=elapsed,
            language=getattr(info, "language", self.config.language),
            language_probability=getattr(info, "language_probability", None),
            segments=len(segments),
        )
