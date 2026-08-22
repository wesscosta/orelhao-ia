from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class AudioConfig(BaseModel):
    sample_rate: int = 16_000
    channels: int = 1
    block_ms: int = 30
    pre_roll_ms: int = 300
    silence_ms: int = 900
    max_record_seconds: float = 15.0
    rms_threshold: float = 0.015
    input_device: int | str | None = None
    output_device: int | str | None = None


class AppConfig(BaseModel):
    name: str = "Orelhão IA"
    environment: str = "development"
    session_timeout_seconds: int = 120
    simulate_hardware: bool = True
    audio: AudioConfig = Field(default_factory=AudioConfig)


def load_config(path: str | Path) -> AppConfig:
    file_path = Path(path)
    if not file_path.exists():
        return AppConfig()
    raw: dict[str, Any] = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
    return AppConfig.model_validate(raw)
