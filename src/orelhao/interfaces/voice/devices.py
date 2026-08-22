from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


DeviceKind = Literal["input", "output"]


@dataclass(frozen=True, slots=True)
class AudioDeviceStatus:
    kind: DeviceKind
    device: int | str | None
    name: str
    channels: int
    native_sample_rate: int
    available: bool
    error: str | None = None


def native_sample_rate(sd: Any, device: int | str | None, kind: DeviceKind) -> int:
    info = sd.query_devices(device, kind)
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
        info = sd.query_devices(device, kind)
        rate = int(round(float(info["default_samplerate"])))
        channel_key = "max_input_channels" if kind == "input" else "max_output_channels"
        max_channels = int(info[channel_key])
        if max_channels < channels:
            raise RuntimeError(f"dispositivo expõe apenas {max_channels} canal(is)")
        checker = sd.check_input_settings if kind == "input" else sd.check_output_settings
        checker(device=device, channels=channels, dtype="int16", samplerate=rate)
        return AudioDeviceStatus(
            kind=kind,
            device=device,
            name=str(info["name"]),
            channels=max_channels,
            native_sample_rate=rate,
            available=True,
        )
    except Exception as exc:
        return AudioDeviceStatus(
            kind=kind,
            device=device,
            name="indisponível",
            channels=0,
            native_sample_rate=0,
            available=False,
            error=str(exc),
        )
