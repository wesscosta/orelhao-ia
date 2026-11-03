"""Leitor do contato seco do gancho no ESP32, protocolo JSON Lines v1.

A polaridade fisica (quando o monofone e retirado) so deve ser definida
apos observacao dos estados com o gancho no suporte e fora dele.
"""
from __future__ import annotations

import argparse
import json
import logging
import time
from dataclasses import dataclass
from typing import Literal

from orelhao.hardware.hook import HookSensor

PROTOCOL = "orelhao.hook.v1"
DEFAULT_PORT = (
    "/dev/serial/by-id/"
    "usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0"
)
Contact = Literal["open", "closed"]
Kind = Literal["state", "change"]


@dataclass(frozen=True, slots=True)
class HookEvent:
    kind: Kind
    contact: Contact
    seq: int
    uptime_ms: int
    gpio: int


def parse_hook_event(line: str | bytes) -> HookEvent | None:
    """Rejeita linhas malformadas/desconhecidas, sem confiar em texto serial."""
    if isinstance(line, bytes):
        try:
            line = line.decode("utf-8")
        except UnicodeDecodeError:
            return None
    if len(line) > 256:
        return None
    try:
        obj = json.loads(line)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(obj, dict):
        return None
    if obj.get("protocol") != PROTOCOL or obj.get("kind") not in ("state", "change"):
        return None
    if obj.get("contact") not in ("open", "closed") or obj.get("gpio") != 27:
        return None
    seq, uptime = obj.get("seq"), obj.get("uptime_ms")
    if type(seq) is not int or type(uptime) is not int:
        return None
    if seq < 0 or uptime < 0:
        return None
    return HookEvent(obj["kind"], obj["contact"], seq, uptime, 27)


class HookSerialAdapter:
    """Atualiza o sensor apenas com mapeamento de polaridade confirmado."""

    def __init__(self, sensor: HookSensor, off_hook_contact: Contact | None = None) -> None:
        self.sensor = sensor
        self.off_hook_contact = off_hook_contact
        self.last_contact: Contact | None = None

    def accept(self, line: str | bytes) -> HookEvent | None:
        event = parse_hook_event(line)
        if event is None:
            return None
        self.last_contact = event.contact
        if self.off_hook_contact is not None:
            self.sensor.set_off_hook(event.contact == self.off_hook_contact)
        return event

    def disconnected(self) -> None:
        """Falha segura: nunca manter a sessao ativa quando a serial cai."""
        self.last_contact = None
        self.sensor.set_off_hook(False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitor do gancho ESP32 via USB serial")
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument(
        "--off-hook-contact",
        choices=["open", "closed"],
        default=None,
        help="Somente apos verificar a mecanica do gancho (padrao: observacao)",
    )
    args = parser.parse_args()
    import serial  # dependência opcional da integração, não do core

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    logger = logging.getLogger(__name__)
    sensor = HookSensor()
    adapter = HookSerialAdapter(sensor, off_hook_contact=args.off_hook_contact)
    while True:
        try:
            with serial.Serial(args.port, 115200, timeout=1, rtscts=False, dsrdtr=False) as port:
                port.dtr = False
                port.rts = False
                logger.info("Serial conectada: %s", args.port)
                while True:
                    line = port.readline(257)
                    was_unknown = adapter.last_contact is None
                    event = adapter.accept(line)
                    if event and (event.kind == "change" or was_unknown):
                        logger.info(
                            "gancho contato=%s kind=%s seq=%d off_hook=%s",
                            event.contact, event.kind, event.seq,
                            sensor.is_off_hook() if adapter.off_hook_contact else "nao_calibrado",
                        )
        except (OSError, serial.SerialException) as exc:
            adapter.disconnected()
            logger.warning("Serial indisponivel: %s (tentando novamente)", exc)
            time.sleep(2)


if __name__ == "__main__":
    main()
