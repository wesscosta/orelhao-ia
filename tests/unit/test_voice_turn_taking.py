"""Garantias do turno: resposta completa antes da proxima escuta."""
from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

from orelhao.hardware.turn_taking import TurnTakingPlayback


def test_wait_before_capture_respects_audio_end_and_echo_guard() -> None:
    times = [10.0]
    sleeps: list[float] = []
    events: list[str] = []

    class Playback:
        def play(self, audio: object) -> None:
            events.append("audio_inicio")
            times[0] += 1.5
            events.append("audio_fim")

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        times[0] += seconds
        events.append("antieco")

    gate = TurnTakingPlayback(Playback(), settle_seconds=0.3,
                              clock=lambda: times[0], sleep=sleep)
    gate.wait_before_capture()
    assert not sleeps
    gate.play(SimpleNamespace(data=b"audio"))  # type: ignore[arg-type]
    gate.wait_before_capture()
    assert sleeps == [pytest.approx(0.3)]
    assert events == ["audio_inicio", "audio_fim", "antieco"]
    gate.wait_before_capture()
    assert len(sleeps) == 1


def test_capture_waits_for_inflight_playback_even_without_echo_delay() -> None:
    playing = threading.Event()
    finish = threading.Event()
    listened = threading.Event()

    class Playback:
        def play(self, audio: object) -> None:
            playing.set()
            assert finish.wait(timeout=2)

    gate = TurnTakingPlayback(Playback(), settle_seconds=0)
    sender = threading.Thread(
        target=lambda: gate.play(SimpleNamespace(data=b"audio")),  # type: ignore[arg-type]
        daemon=True,
    )
    sender.start()
    assert playing.wait(timeout=1)
    receiver = threading.Thread(target=lambda: (gate.wait_before_capture(), listened.set()),
                                daemon=True)
    receiver.start()
    assert not listened.wait(timeout=0.05)
    finish.set()
    sender.join(timeout=2)
    receiver.join(timeout=2)
    assert not sender.is_alive() and not receiver.is_alive()
    assert listened.is_set()


def test_failed_playback_fails_closed_without_new_capture() -> None:
    class FailingPlayback:
        def play(self, audio: object) -> None:
            raise OSError("falha no player")

    gate = TurnTakingPlayback(FailingPlayback(), settle_seconds=0)
    with pytest.raises(OSError, match="falha"):
        gate.play(SimpleNamespace(data=b"audio"))  # type: ignore[arg-type]
    with pytest.raises(RuntimeError, match="captura bloqueada"):
        gate.wait_before_capture()


def test_invalid_negative_guard_is_rejected() -> None:
    with pytest.raises(ValueError):
        TurnTakingPlayback(SimpleNamespace(play=lambda _: None), settle_seconds=-0.1)
