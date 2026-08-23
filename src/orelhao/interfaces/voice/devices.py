from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


DeviceKind = Literal["input", "output"]


@dataclass(frozen=True, slots=True)
class AudioDeviceStatus:
    kind: DeviceKind
    device: int | str | None
    resolved_index: int | None
    name: str
    channels: int
    native_sample_rate: int
    available: bool
    error: str | None = None


def _channel_key(kind: DeviceKind) -> str:
    return "max_input_channels" if kind == "input" else "max_output_channels"


def resolve_device(sd: Any, device: int | str | None, kind: DeviceKind) -> int | None:
    """Resolve a configured audio selector to a current PortAudio index.

    Integer indices remain supported for diagnostics/backwards compatibility, but a
    textual device name is preferred for appliances because PortAudio indices can
    change after boot, hotplug or changes in HDMI/USB devices.
    """
    if device is None:
        return None

    devices = list(sd.query_devices())
    key = _channel_key(kind)

    if isinstance(device, int):
        if device < 0 or device >= len(devices):
            raise ValueError(f"Índice de áudio inexistente: {device}")
        info = devices[device]
        if int(info[key]) <= 0:
            raise ValueError(f"Dispositivo {device} não possui canais de {kind}: {info['name']!r}")
        return device

    selector = device.strip().casefold()
    if not selector:
        return None

    capable = [
        (index, info)
        for index, info in enumerate(devices)
        if int(info[key]) > 0
    ]
    exact = [(index, info) for index, info in capable if str(info["name"]).casefold() == selector]
    if len(exact) == 1:
        return exact[0][0]

    partial = [(index, info) for index, info in capable if selector in str(info["name"]).casefold()]
    if len(partial) == 1:
        return partial[0][0]
    if not partial:
        raise ValueError(f"Nenhum dispositivo de {kind} corresponde a {device!r}")

    names = ", ".join(f"{i}:{info['name']}" for i, info in partial[:5])
    raise ValueError(f"Seletor de áudio ambíguo {device!r}: {names}")


def native_sample_rate(sd: Any, device: int | str | None, kind: DeviceKind) -> int:
    resolved = resolve_device(sd, device, kind)
    info = sd.query_devices(resolved, kind)
    value = float(info["default_samplerate"])
    if value <= 0:
        raise RuntimeError(f"Dispositivo de {kind} informou sample rate inválido: {value}")
    return int(round(value))


def inspect_device(
    sd: Any,
    device: int | str | None,
    kind: DeviceKind,
    channels: int = 1,
) -> AudioDeviceStatus:
    try:
        resolved = resolve_device(sd, device, kind)
        info = sd.query_devices(resolved, kind)
        rate = int(round(float(info["default_samplerate"])))
        channel_key = _channel_key(kind)
        max_channels = int(info[channel_key])
        if max_channels < channels:
            raise RuntimeError(f"dispositivo expõe apenas {max_channels} canal(is)")
        checker = sd.check_input_settings if kind == "input" else sd.check_output_settings
        checker(device=resolved, channels=channels, dtype="int16", samplerate=rate)
        return AudioDeviceStatus(
            kind=kind, device=device, resolved_index=resolved, name=str(info["name"]),
            channels=max_channels, native_sample_rate=rate, available=True,
        )
    except Exception as exc:
        return AudioDeviceStatus(
            kind=kind, device=device, resolved_index=None, name="indisponível",
            channels=0, native_sample_rate=0, available=False, error=str(exc),
        )
