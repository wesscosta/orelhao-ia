from __future__ import annotations

from array import array
from dataclasses import dataclass
from math import sqrt
from statistics import median
from typing import Iterable


@dataclass(slots=True)
class EnergyVAD:
    """VAD por energia com threshold fixo.

    Mantido como primitiva simples e útil em testes. Em produção a captura usa
    ``AdaptiveEnergyVAD`` para calibrar o ruído do ambiente antes de ouvir a fala.
    """

    rms_threshold: float = 0.015

    @staticmethod
    def rms(pcm16: bytes) -> float:
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


@dataclass(slots=True)
class AdaptiveEnergyVAD:
    """VAD offline com calibração de noise floor.

    O threshold é derivado da mediana do RMS dos blocos de calibração. A mediana
    reduz o impacto de picos esporádicos e evita calibrar o terminal para um único
    computador/microfone.
    """

    threshold_multiplier: float = 3.0
    min_threshold: float = 0.006
    max_threshold: float = 0.08
    noise_floor: float = 0.0
    threshold: float = 0.006

    def calibrate(self, blocks: Iterable[bytes]) -> float:
        levels = [EnergyVAD.rms(block) for block in blocks if block]
        self.noise_floor = median(levels) if levels else 0.0
        candidate = self.noise_floor * self.threshold_multiplier
        self.threshold = min(self.max_threshold, max(self.min_threshold, candidate))
        return self.threshold

    def is_speech(self, pcm16: bytes) -> bool:
        return EnergyVAD.rms(pcm16) >= self.threshold
