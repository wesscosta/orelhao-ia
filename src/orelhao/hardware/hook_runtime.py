"""Hook ESP32 -> disposable voice call, fail-closed on USB loss/hangup."""
from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

from orelhao.hardware.live_monitor import finish_session, start_session
from orelhao.hardware.serial_hook import DEFAULT_PORT, HookEvent, parse_hook_event

LOG = logging.getLogger(__name__)
HEARTBEAT_TIMEOUT = 15.0
MIN_CONTACT_HOLD_SECONDS = 0.75
_MONITOR_SESSIONS: dict[int, str] = {}


def audio_ready() -> bool:
    """Do not start a call if the analog input/output routes are missing or muted."""
    if not os.access(Path("/dev/snd/controlC0"), os.R_OK | os.W_OK):
        return False
    try:
        import pulsectl  # type: ignore[import-untyped]
    except ImportError:
        return False
    try:
        with pulsectl.Pulse("lumi-hook-audio-guard") as pulse:
            sink = next(s for s in pulse.sink_list() if s.name.startswith("alsa_output."))
            source = next(s for s in pulse.source_list() if s.name.startswith("alsa_input."))
            return bool(
                sink.port_active
                and sink.port_active.name == "analog-output-headphones"
                and not sink.mute
                and source.port_active
                and source.port_active.name == "analog-input-headset-mic"
                and not source.mute
            )
    except (OSError, RuntimeError, StopIteration, pulsectl.PulseError):
        return False


def ensure_audio_ready() -> bool:
    """Repair a reverted PipeWire input route before a call; never bypass guard."""
    if audio_ready():
        return True
    script = Path(__file__).resolve().parents[3] / "scripts" / "configure_headset_audio.py"
    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=18,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        LOG.warning("Falha ao recuperar a rota de áudio: %s", exc)
        return False
    if result.returncode:
        LOG.warning("Rota de áudio indisponível: %s", result.stderr[-300:])
        return False
    return audio_ready()


def spawn_voice() -> subprocess.Popen[bytes]:
    session_id = start_session()
    env = os.environ.copy()
    env["ORELHAO_MONITOR_SESSION_ID"] = session_id
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "orelhao.hardware.voice_worker"],
            stdin=subprocess.DEVNULL, start_new_session=True, env=env,
        )
    except OSError:
        finish_session(session_id, "startup_error")
        raise
    _MONITOR_SESSIONS[proc.pid] = session_id
    return proc


def stop_voice(proc: subprocess.Popen[bytes]) -> None:
    """Terminate the entire session group, including the recorder and player."""
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=1)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=2)


class HookCallController:
    def __init__(
        self,
        *,
        spawn: Callable[[], subprocess.Popen[bytes]] = spawn_voice,
        stop: Callable[[subprocess.Popen[bytes]], None] = stop_voice,
        ready: Callable[[], bool] = ensure_audio_ready,
    ) -> None:
        self._spawn = spawn
        self._stop = stop
        self._ready = ready
        self._proc: subprocess.Popen[bytes] | None = None
        self.contact: str | None = None
        self.armed = False
        self._pending_since: float | None = None
        self.last_seen = time.monotonic()

    def handle(self, event: HookEvent) -> None:
        self.last_seen = time.monotonic()
        previous = self.contact
        self.contact = event.contact
        if event.contact == "open":
            self.armed = True
            self._pending_since = None
            self.hangup("contato_aberto")
        elif event.kind == "change" and previous == "open" and self.armed:
            # A jumper can bounce across the contacts: require a stable hold.
            self._pending_since = time.monotonic()

    def hangup(self, reason: str) -> None:
        if self._proc is not None:
            LOG.info("atendimento_interrompido motivo=%s", reason)
            proc = self._proc
            try:
                self._stop(proc)
            finally:
                session_id = _MONITOR_SESSIONS.pop(getattr(proc, "pid", -1), None)
                if isinstance(session_id, str):
                    finish_session(session_id, reason)
                self._proc = None

    def check(self) -> None:
        if (
            self._pending_since is not None
            and self.contact == "closed"
            and self.armed
            and time.monotonic() - self._pending_since >= MIN_CONTACT_HOLD_SECONDS
        ):
            self._pending_since = None
            self.armed = False
            if not self._ready():
                LOG.warning("audio_indisponivel: atendimento nao iniciado")
            elif self._proc is None:
                self._proc = self._spawn()
                LOG.info("gancho_fechado: atendimento iniciado pid=%d", self._proc.pid)
        if self._proc is not None and self._proc.poll() is not None:
            LOG.info("atendimento_finalizado: aguarda abertura do gancho")
            session_id = _MONITOR_SESSIONS.pop(getattr(self._proc, "pid", -1), None)
            if isinstance(session_id, str):
                finish_session(session_id, "atendimento_finalizado")
            self._proc = None
        if time.monotonic() - self.last_seen > HEARTBEAT_TIMEOUT and self.contact is not None:
            LOG.warning("esp32_sem_heartbeat: encerrando sessão")
            self.disconnected()

    def disconnected(self) -> None:
        self.hangup("serial_perdida")
        self.contact = None
        self.armed = False
        self._pending_since = None
        self.last_seen = time.monotonic()


def main() -> None:
    import serial

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    controller = HookCallController()
    while True:
        try:
            with serial.Serial(DEFAULT_PORT, 115200, timeout=1, rtscts=False, dsrdtr=False) as port:
                port.dtr = False
                port.rts = False
                LOG.info("gancho_usb_conectado")
                while True:
                    event = parse_hook_event(port.readline(257))
                    if event is not None:
                        previous = controller.contact
                        controller.handle(event)
                        if event.kind == "change" or previous is None:
                            LOG.info("gancho contato=%s kind=%s", event.contact, event.kind)
                    controller.check()
        except (OSError, serial.SerialException) as exc:
            controller.disconnected()
            LOG.warning("gancho_usb_desconectado: %s", exc)
            time.sleep(2)
        except (KeyboardInterrupt, SystemExit):
            controller.disconnected()
            raise


if __name__ == "__main__":
    main()
