from dataclasses import dataclass


@dataclass(slots=True)
class HealthStatus:
    ok: bool = True
    message: str = "ok"
