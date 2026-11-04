"""Coordena reproducoes e inicio da proxima captura de voz.

O mesmo lock cobre toda a reproducao bloqueante e o intervalo antieco,
impedindo uma nova captura enquanto o Lumi ainda esta falando.
"""
from __future__ import annotations

import threading
import time
from collections.abc import Callable

from orelhao.interfaces.voice.audio import PCM16Audio
from orelhao.interfaces.voice.playback import AudioPlayback

POST_PLAYBACK_SETTLE_SECONDS = 0.3


class TurnTakingPlayback:
    """Serializa a saida de voz e libera o microfone apenas apos o audio."""

    def __init__(
        self,
        playback: AudioPlayback,
        *,
        settle_seconds: float = POST_PLAYBACK_SETTLE_SECONDS,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if settle_seconds < 0:
            raise ValueError("intervalo antieco deve ser nao negativo")
        self._playback = playback
        self._settle_seconds = settle_seconds
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._last_playback_end: float | None = None
        self._failed = False

    def play(self, audio: PCM16Audio) -> None:
        """Nao libera o proximo turno antes de o backend retornar."""
        with self._lock:
            if self._failed:
                raise RuntimeError("reproducao anterior falhou; captura bloqueada")
            try:
                self._playback.play(audio)
            except Exception:
                self._failed = True
                raise
            self._last_playback_end = self._clock()

    def wait_before_capture(self) -> None:
        """Espera o fim do audio em curso e, se preciso, o eco residual."""
        with self._lock:
            if self._failed:
                raise RuntimeError("reproducao falhou; captura bloqueada")
            if self._last_playback_end is None:
                return
            remaining = self._last_playback_end + self._settle_seconds - self._clock()
            if remaining > 0:
                self._sleep(remaining)
