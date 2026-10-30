"""Catálogo fechado de vozes Piper para a bancada experimental.

A seleção é feita por requisição, sem alterar a configuração global nem
aceitar caminhos de modelo fornecidos pelo navegador.
"""
from __future__ import annotations

import threading
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from orelhao.config import TTSConfig
from orelhao.services.tts.service import PiperTTSService, TTSService

VoiceId = Literal["cadu", "faber"]
_VOICES: dict[str, tuple[str, str]] = {
    "cadu": ("Piper Cadu (original)", "models/tts/pt_BR-cadu-medium.onnx"),
    "faber": ("Piper Faber (experimental)", "models/tts/pt_BR-faber-medium.onnx"),
}


@dataclass(frozen=True, slots=True)
class VoiceInfo:
    id: str
    label: str


def voice_options() -> tuple[VoiceInfo, ...]:
    return tuple(VoiceInfo(key, value[0]) for key, value in _VOICES.items())


def validate_voice_id(voice: str) -> str:
    if voice not in _VOICES:
        raise ValueError("Voz inválida. Opções disponíveis: cadu, faber.")
    return voice


class WorkbenchPiperVoices:
    def __init__(
        self,
        config: TTSConfig,
        *,
        injected: Mapping[str, TTSService] | None = None,
    ) -> None:
        self._config = config
        self._services: dict[str, TTSService] = dict(injected or {})
        self._lock = threading.Lock()

    def get(self, voice: str) -> TTSService:
        voice = validate_voice_id(voice)
        with self._lock:
            if voice not in self._services:
                model = _VOICES[voice][1]
                settings = self._config.model_copy(
                    update={"model": model, "config": model + ".json"},
                )
                self._services[voice] = PiperTTSService(settings)
            return self._services[voice]
