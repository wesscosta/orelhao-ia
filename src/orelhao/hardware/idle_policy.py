"""Política determinística de silêncio e pausa da ligação física.

Cada tentativa sem fala é limitada pelo VAD, sem nova inferência ou TTS em loop.
A política nunca encerra por inatividade durante a reprodução da fala do Lumi.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

IdleDecision = Literal["prompt", "wait", "close"]


@dataclass
class CallIdlePolicy:
    """Encerramento rápido, com prazo maior quando a pausa foi solicitada."""

    regular_silent_captures: int = 2
    paused_silent_captures: int = 4
    paused: bool = False
    consecutive_silences: int = 0

    def __post_init__(self) -> None:
        if self.regular_silent_captures < 2 or self.paused_silent_captures < 1:
            raise ValueError("limites de silêncio inválidos")

    def on_phrase(self, *, requested_pause: bool) -> None:
        """Uma frase inteligível reativa a conversa, inclusive após pausa."""
        self.paused = requested_pause
        self.consecutive_silences = 0

    def on_missing_speech(self) -> IdleDecision:
        """Chamado após VAD silencioso ou STT rejeitado, nunca durante TTS."""
        self.consecutive_silences += 1
        maximum = (
            self.paused_silent_captures if self.paused
            else self.regular_silent_captures
        )
        if self.consecutive_silences >= maximum:
            return "close"
        if self.paused:
            return "wait"
        return "prompt" if self.consecutive_silences == 1 else "wait"
