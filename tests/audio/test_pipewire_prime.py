"""Pré-aquecimento da entrada do monofone sem capturar áudio de usuário."""
from __future__ import annotations

import signal
import subprocess
from pathlib import Path

import pytest

from orelhao.config import AudioConfig
from orelhao.interfaces.voice.capture import PipeWireAudioCapture


class Recorder:
    def __init__(self, *, premature: bool = False) -> None:
        self.premature = premature
        self.signal: int | None = None
        self.wait_timeouts: list[float] = []

    def wait(self, timeout: float | None = None) -> int:
        self.wait_timeouts.append(timeout or 0)
        if self.premature or self.signal is not None:
            return 0
        raise subprocess.TimeoutExpired("pw-record", timeout)

    def poll(self) -> int | None:
        return 0 if self.signal is not None or self.premature else None

    def send_signal(self, sig: int) -> None:
        self.signal = sig

    def kill(self) -> None:
        self.signal = signal.SIGKILL


def test_pipewire_prime_termina_recorder_e_apaga_audio_temporario(monkeypatch) -> None:
    recorder = Recorder()
    paths: list[Path] = []

    def fake_popen(command, **_kwargs):
        paths.append(Path(command[-1]))
        paths[-1].write_bytes(b"transiente que nao pode persistir")
        return recorder

    monkeypatch.setattr("shutil.which", lambda _executable: "/usr/bin/pw-record")
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    capture = PipeWireAudioCapture(AudioConfig(pipewire_warmup_seconds=2.6))
    capture.prime()

    assert recorder.wait_timeouts[0] == pytest.approx(2.6)
    assert recorder.signal == signal.SIGINT
    assert paths and not paths[0].exists()


def test_pipewire_prime_desabilitado_nao_inicia_processo(monkeypatch) -> None:
    def no_spawn(*_args, **_kwargs):
        raise AssertionError("warm-up foi desabilitado")

    monkeypatch.setattr(subprocess, "Popen", no_spawn)
    capture = PipeWireAudioCapture(AudioConfig(pipewire_warmup_seconds=0))
    capture.prime()


def test_pipewire_prime_falha_rapida_e_remocao_do_audio(monkeypatch) -> None:
    recorder = Recorder(premature=True)
    paths: list[Path] = []

    def fake_popen(command, **_kwargs):
        paths.append(Path(command[-1]))
        paths[-1].write_bytes(b"sem valor para a chamada")
        return recorder

    monkeypatch.setattr("shutil.which", lambda _executable: "/usr/bin/pw-record")
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    capture = PipeWireAudioCapture(AudioConfig(pipewire_warmup_seconds=2.6))
    with pytest.raises(RuntimeError, match="prematuramente"):
        capture.prime()
    assert paths and not paths[0].exists()
