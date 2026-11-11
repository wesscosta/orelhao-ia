"""Piper local residente em memória, sem subprocessos nem WAV temporário.

É uma alternativa opt-in à execução isolada via CLI. O lock evita que chamadas
concorrentes disputem a mesma sessão ONNX. O cache vive só durante a chamada.
"""
from __future__ import annotations

import threading
from time import perf_counter
from typing import Any

from orelhao.config import TTSConfig
from orelhao.interfaces.voice.audio import PCM16Audio
from orelhao.runtime_paths import resolve_project_path
from orelhao.services.tts.service import SynthesisResult


class PiperResidentTTSService:
    def __init__(self, config: TTSConfig) -> None:
        self.config = config
        self._lock = threading.RLock()
        self._voice: Any | None = None

    def prepare(self) -> float:
        """Carrega a sessão ONNX uma única vez; retorna o custo em segundos."""
        start = perf_counter()
        with self._lock:
            if self._voice is None:
                try:
                    from piper.voice import PiperVoice
                except ImportError as exc:
                    raise RuntimeError("piper-tts não instalado no ambiente") from exc
                model_path = resolve_project_path(self.config.model)
                config_path = (
                    resolve_project_path(self.config.config) if self.config.config else None
                )
                if not model_path.is_file():
                    raise RuntimeError(f"Modelo TTS não encontrado: {model_path}")
                if config_path is not None and not config_path.is_file():
                    raise RuntimeError(f"Config do modelo TTS não encontrado: {config_path}")
                self._voice = PiperVoice.load(model_path, config_path=config_path)
        return perf_counter() - start

    def synthesize_result(self, text: str) -> SynthesisResult:
        clean = text.strip()
        if not clean:
            raise ValueError("Texto para TTS não pode ser vazio")
        started = perf_counter()
        # O mesmo lock protege carregamento inicial e inferência.
        with self._lock:
            self.prepare()
            from piper.config import SynthesisConfig

            cfg = SynthesisConfig(
                speaker_id=self.config.speaker,
                length_scale=self.config.length_scale,
                noise_scale=self.config.noise_scale,
                noise_w_scale=self.config.noise_w,
            )
            samples: list[bytes] = []
            sample_rate: int | None = None
            voice = self._voice
            if voice is None:
                raise RuntimeError("Piper residente não inicializado")
            for chunk in voice.synthesize(clean, syn_config=cfg):
                if chunk.sample_width != 2 or chunk.sample_channels != 1:
                    raise RuntimeError("Piper residente entregou PCM incompatível")
                if sample_rate is not None and chunk.sample_rate != sample_rate:
                    raise RuntimeError("Piper residente alterou a taxa durante a síntese")
                sample_rate = chunk.sample_rate
                samples.append(chunk.audio_int16_bytes)
            if sample_rate is None or not samples:
                raise RuntimeError("Piper residente não produziu áudio")
        audio = PCM16Audio(data=b"".join(samples), sample_rate=sample_rate, channels=1)
        elapsed = perf_counter() - started
        duration = audio.duration_seconds
        return SynthesisResult(
            audio=audio,
            elapsed_seconds=elapsed,
            audio_seconds=duration,
            real_time_factor=elapsed / duration if duration > 0 else float("inf"),
        )

    def synthesize(self, text: str) -> PCM16Audio:
        return self.synthesize_result(text).audio
