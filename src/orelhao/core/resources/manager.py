from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ResourceSnapshot:
    cpu_percent: float | None = None
    ram_used_mb: float | None = None
    vram_used_mb: float | None = None


class ResourceManager:
    """Contrato inicial para decisões futuras de CPU/RAM/VRAM.

    Na v0.1 ainda não gerencia modelos; serve para impedir acoplamento do core
    a uma GPU ou runtime específico.
    """

    def snapshot(self) -> ResourceSnapshot:
        return ResourceSnapshot()
