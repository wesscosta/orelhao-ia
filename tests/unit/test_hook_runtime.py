"""Contract tests: GPIO close must not start an unsafe/duplicate voice call."""
from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from orelhao.hardware.hook_runtime import HookCallController
from orelhao.hardware.serial_hook import Contact, HookEvent, Kind


@dataclass
class FakeProc:
    pid: int = 42
    exited: bool = False

    def poll(self) -> int | None:
        return 0 if self.exited else None


def event(contact: str, kind: str = "change") -> HookEvent:
    return HookEvent(kind=cast("Kind", kind), contact=cast("Contact", contact), seq=1, uptime_ms=100, gpio=27)


def test_open_then_closed_starts_once_and_open_terminates() -> None:
    spawned: list[FakeProc] = []
    stopped: list[FakeProc] = []

    def spawn() -> FakeProc:
        p = FakeProc()
        spawned.append(p)
        return p

    ctl = HookCallController(spawn=spawn, stop=stopped.append, ready=lambda: True)  # type: ignore[arg-type]
    ctl.handle(event("closed", "state"))
    assert not spawned  # Boot in closed state never calls automatically.
    ctl.handle(event("open", "state"))
    ctl.handle(event("closed"))
    ctl.handle(event("closed"))
    assert not spawned
    assert ctl._pending_since is not None
    ctl._pending_since -= 1
    ctl.check()
    assert len(spawned) == 1
    ctl.handle(event("open"))
    assert stopped == spawned
    ctl.handle(event("closed"))
    assert ctl._pending_since is not None
    ctl._pending_since -= 1
    ctl.check()
    assert len(spawned) == 2


def test_audio_unavailable_blocks_call() -> None:
    spawned: list[FakeProc] = []
    ctl = HookCallController(spawn=lambda: spawned.append(FakeProc()), ready=lambda: False)  # type: ignore[arg-type]
    ctl.handle(event("open", "state"))
    ctl.handle(event("closed"))
    assert ctl._pending_since is not None
    ctl._pending_since -= 1
    ctl.check()
    assert not spawned


def test_usb_timeout_hangs_up_and_requires_new_open() -> None:
    proc = FakeProc()
    stopped: list[FakeProc] = []
    ctl = HookCallController(spawn=lambda: proc, stop=stopped.append, ready=lambda: True)  # type: ignore[arg-type]
    ctl.handle(event("open", "state"))
    ctl.handle(event("closed"))
    assert ctl._pending_since is not None
    ctl._pending_since -= 1
    ctl.check()
    ctl.last_seen -= 20
    ctl.check()
    assert stopped == [proc] and ctl.contact is None
    ctl.handle(event("closed", "state"))
    assert ctl.contact == "closed" and not ctl.armed


def test_worker_exit_does_not_retrigger_in_closed_state() -> None:
    proc = FakeProc()
    started: list[FakeProc] = []
    ctl = HookCallController(
        spawn=lambda: (started.append(proc), proc)[1], ready=lambda: True,  # type: ignore[arg-type]
    )
    ctl.handle(event("open", "state"))
    ctl.handle(event("closed"))
    assert ctl._pending_since is not None
    ctl._pending_since -= 1
    ctl.check()
    proc.exited = True
    ctl.check()
    ctl.handle(event("closed", "state"))
    assert len(started) == 1


def test_audio_route_repair_and_fail_closed(monkeypatch) -> None:
    from types import SimpleNamespace

    from orelhao.hardware import hook_runtime

    attempts: list[object] = []
    monkeypatch.setattr(hook_runtime, "audio_ready", lambda: bool(attempts))

    def run(*args, **kwargs):
        attempts.append((args, kwargs))
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(hook_runtime.subprocess, "run", run)
    assert hook_runtime.ensure_audio_ready()
    assert len(attempts) == 1
    assert hook_runtime.ensure_audio_ready()
    assert len(attempts) == 1

    monkeypatch.setattr(hook_runtime, "audio_ready", lambda: False)
    assert not hook_runtime.ensure_audio_ready()


def test_audio_route_repair_failure(monkeypatch) -> None:
    from types import SimpleNamespace

    from orelhao.hardware import hook_runtime

    monkeypatch.setattr(hook_runtime, "audio_ready", lambda: False)
    monkeypatch.setattr(
        hook_runtime.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stderr="rota inexistente"),
    )
    assert not hook_runtime.ensure_audio_ready()


def test_fast_contact_bounce_never_starts_a_call() -> None:
    spawned: list[FakeProc] = []
    ctl = HookCallController(spawn=lambda: spawned.append(FakeProc()), ready=lambda: True)  # type: ignore[arg-type]
    ctl.handle(event("open", "state"))
    for _ in range(5):
        ctl.handle(event("closed"))
        ctl.handle(event("open"))
        ctl.check()
    assert not spawned
    assert ctl._pending_since is None


def test_audio_ready_rejects_headphone_mic_and_accepts_headset_mic(monkeypatch) -> None:
    from types import SimpleNamespace

    import pulsectl

    from orelhao.hardware import hook_runtime

    selected = {"port": "analog-input-headphone-mic"}

    class FakePulse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def sink_list(self):
            return [SimpleNamespace(
                name="alsa_output.test",
                port_active=SimpleNamespace(name="analog-output-headphones"),
                mute=False,
            )]

        def source_list(self):
            return [SimpleNamespace(
                name="alsa_input.test",
                port_active=SimpleNamespace(name=selected["port"]),
                mute=False,
            )]

    monkeypatch.setattr(hook_runtime.os, "access", lambda *_args: True)
    monkeypatch.setattr(pulsectl, "Pulse", lambda *_args: FakePulse())

    assert not hook_runtime.audio_ready()
    selected["port"] = "analog-input-headset-mic"
    assert hook_runtime.audio_ready()
