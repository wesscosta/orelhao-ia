from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from array import array


@dataclass(slots=True)
class EnergyVAD:
    """VAD simples por energia para validar o pipeline de áudio da v0.1.

    Não é a decisão final de VAD. Ele é deliberadamente leve, offline e sem modelo,
    adequado para benchmarking inicial do microfone/monofone.
    """

    rms_threshold: float = 0.015

    def rms(self, pcm16: bytes) -> float:
        if not pcm16:
            return 0.0
        samples = array("h")
        samples.frombytes(pcm16)
        if not samples:
            return 0.0
        scale = 32768.0
        energy = sum((sample / scale) ** 2 for sample in samples) / len(samples)
        return sqrt(energy)

    def is_speech(self, pcm16: bytes) -> bool:
        return self.rms(pcm16) >= self.rms_threshold
