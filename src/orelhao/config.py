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
    max_record_seconds: float = 30.0
    rms_threshold: float = 0.015  # legado/fallback para VAD fixo
    adaptive_vad: bool = True
    vad_calibration_ms: int = 700
    speech_start_timeout_seconds: float = 8.0
    vad_threshold_multiplier: float = 3.0
    vad_min_threshold: float = 0.006
    vad_max_threshold: float = 0.08
    input_device: int | str | None = None
    output_device: int | str | None = None


class STTConfig(BaseModel):
    backend: str = "faster-whisper"
    model: str = "small"
    language: str = "pt"
    device: str = "auto"
    compute_type: str = "default"
    beam_size: int = 1
    cpu_threads: int = 0
    num_workers: int = 1
    fallback_to_cpu: bool = True
    cpu_fallback_compute_type: str = "int8"


class AppConfig(BaseModel):
    name: str = "Orelhão IA"
    environment: str = "development"
    session_timeout_seconds: int = 120
    simulate_hardware: bool = True
    audio: AudioConfig = Field(default_factory=AudioConfig)
    stt: STTConfig = Field(default_factory=STTConfig)


def load_config(path: str | Path) -> AppConfig:
    file_path = Path(path)
    if not file_path.exists():
        return AppConfig()
    raw: dict[str, Any] = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
    return AppConfig.model_validate(raw)
