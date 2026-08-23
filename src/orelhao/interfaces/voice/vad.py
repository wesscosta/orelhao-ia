from __future__ import annotations

from array import array
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from math import sqrt
from statistics import median
from typing import Iterable


@dataclass(slots=True)
class EnergyVAD:
    """VAD por energia com threshold fixo."""

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
    """VAD offline com calibração robusta de noise floor.

    Usa a mediana da metade mais silenciosa dos blocos de calibração. Isso evita
    que uma palavra, movimento ou clique durante a calibração seja tratado como
    ruído ambiente permanente e eleve o threshold para o teto.
    """

    threshold_multiplier: float = 1.8
    min_threshold: float = 0.006
    max_threshold: float = 0.05
    noise_floor: float = 0.0
    threshold: float = 0.006

    def calibrate(self, blocks: Iterable[bytes]) -> float:
        levels = sorted(EnergyVAD.rms(block) for block in blocks if block)
        if levels:
            quiet_count = max(1, (len(levels) + 1) // 2)
            quiet_levels = levels[:quiet_count]
            self.noise_floor = median(quiet_levels)
        else:
            self.noise_floor = 0.0
        candidate = self.noise_floor * self.threshold_multiplier
        self.threshold = min(self.max_threshold, max(self.min_threshold, candidate))
        return self.threshold

    def is_speech(self, pcm16: bytes) -> bool:
        return EnergyVAD.rms(pcm16) >= self.threshold


class SpeechGateState(str, Enum):
    WAITING = "waiting"
    SPEAKING = "speaking"
    COMPLETE = "complete"


@dataclass(slots=True)
class SpeechGate:
    """Debounce temporal para início/fim de fala.

    Um pico isolado não inicia a sessão: são necessários vários blocos de voz
    consecutivos. Após o início, pausas curtas são toleradas. Um falso início
    curto retorna ao estado WAITING em vez de avançar para STT.
    """

    start_blocks_required: int
    min_voiced_blocks: int
    end_silence_blocks_required: int
    false_start_silence_blocks: int
    state: SpeechGateState = SpeechGateState.WAITING
    consecutive_speech: int = 0
    voiced_blocks: int = 0
    silence_blocks: int = 0

    def observe(self, is_speech: bool) -> str | None:
        if self.state is SpeechGateState.COMPLETE:
            return "speech_ended"

        if self.state is SpeechGateState.WAITING:
            if is_speech:
                self.consecutive_speech += 1
                if self.consecutive_speech >= self.start_blocks_required:
                    self.state = SpeechGateState.SPEAKING
                    self.voiced_blocks = self.consecutive_speech
                    self.silence_blocks = 0
                    return "speech_started"
            else:
                self.consecutive_speech = 0
            return None

        if is_speech:
            self.voiced_blocks += 1
            self.silence_blocks = 0
            return None

        self.silence_blocks += 1
        if (
            self.voiced_blocks < self.min_voiced_blocks
            and self.silence_blocks >= self.false_start_silence_blocks
        ):
            self.reset()
            return "false_start"

        if (
            self.voiced_blocks >= self.min_voiced_blocks
            and self.silence_blocks >= self.end_silence_blocks_required
        ):
            self.state = SpeechGateState.COMPLETE
            return "speech_ended"
        return None

    def reset(self) -> None:
        self.state = SpeechGateState.WAITING
        self.consecutive_speech = 0
        self.voiced_blocks = 0
        self.silence_blocks = 0


@dataclass(slots=True)
class WebRTCVAD:
    """VAD de fala baseado no algoritmo WebRTC.

    Entrada: PCM16 mono, 8/16/32/48 kHz, frames de 10/20/30 ms.
    RMS permanece apenas como telemetria e calibração.
    """

    aggressiveness: int = 2
    _vad: object = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.aggressiveness not in (0, 1, 2, 3):
            raise ValueError("vad_aggressiveness deve estar entre 0 e 3")
        try:
            import webrtcvad
        except ImportError as exc:
            raise RuntimeError(
                "WebRTC VAD não instalado. Execute: pip install -e '.[vad]'"
            ) from exc
        self._vad = webrtcvad.Vad(self.aggressiveness)

    def is_speech(self, pcm16: bytes, sample_rate: int) -> bool:
        try:
            return bool(self._vad.is_speech(pcm16, sample_rate))
        except Exception as exc:
            raise RuntimeError(
                f"Frame incompatível com WebRTC VAD: {len(pcm16)} bytes @ {sample_rate} Hz"
            ) from exc


@dataclass(slots=True)
class HysteresisSpeechGate:
    """Endpointing por votação temporal e histerese.

    Início e fim usam janelas independentes. Isso evita exigir frames de fala
    estritamente consecutivos e permite tolerar pausas naturais, ao mesmo tempo
    que ruído residual esparso não mantém a gravação aberta indefinidamente.
    """

    start_window_blocks: int
    start_ratio: float
    min_voiced_blocks: int
    end_window_blocks: int
    end_ratio: float
    state: SpeechGateState = SpeechGateState.WAITING
    voiced_blocks: int = 0
    _start_window: deque[bool] = field(init=False)
    _end_window: deque[bool] = field(init=False)

    def __post_init__(self) -> None:
        self.start_window_blocks = max(1, self.start_window_blocks)
        self.end_window_blocks = max(1, self.end_window_blocks)
        self._start_window = deque(maxlen=self.start_window_blocks)
        self._end_window = deque(maxlen=self.end_window_blocks)

    @staticmethod
    def _ratio(values: deque[bool]) -> float:
        return (sum(values) / len(values)) if values else 0.0

    def observe(self, is_speech: bool) -> str | None:
        if self.state is SpeechGateState.COMPLETE:
            return "speech_ended"

        if self.state is SpeechGateState.WAITING:
            self._start_window.append(is_speech)
            if (
                len(self._start_window) == self.start_window_blocks
                and self._ratio(self._start_window) >= self.start_ratio
            ):
                self.state = SpeechGateState.SPEAKING
                self.voiced_blocks = sum(self._start_window)
                self._end_window.clear()
                return "speech_started"
            return None

        self._end_window.append(is_speech)
        if is_speech:
            self.voiced_blocks += 1

        if (
            self.voiced_blocks >= self.min_voiced_blocks
            and len(self._end_window) == self.end_window_blocks
            and self._ratio(self._end_window) <= self.end_ratio
        ):
            self.state = SpeechGateState.COMPLETE
            return "speech_ended"
        return None

    def reset(self) -> None:
        self.state = SpeechGateState.WAITING
        self.voiced_blocks = 0
        self._start_window.clear()
        self._end_window.clear()
