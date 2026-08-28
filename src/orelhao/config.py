from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class AudioConfig(BaseModel):
    sample_rate: int = 16_000
    channels: int = 1
    block_ms: int = 30
    pre_roll_ms: int = 300
    silence_ms: int = 1800
    max_record_seconds: float = 30.0
    rms_threshold: float = 0.015  # legado/fallback para VAD fixo
    adaptive_vad: bool = True
    vad_calibration_ms: int = 700
    speech_start_timeout_seconds: float = 12.0
    speech_start_min_ms: int = 180
    min_speech_ms: int = 360
    false_start_silence_ms: int = 450
    capture_backend: str = "pipewire"
    pipewire_executable: str = "pw-record"
    pipewire_target: str | None = None
    vad_threshold_multiplier: float = 1.8  # telemetria RMS; não decide fala no backend webrtc
    vad_min_threshold: float = 0.006
    vad_max_threshold: float = 0.05
    vad_backend: str = "webrtc"
    vad_aggressiveness: int = 2
    vad_start_window_ms: int = 300
    vad_start_ratio: float = 0.55
    vad_end_window_ms: int = 1500
    vad_end_ratio: float = 0.10
    vad_post_roll_ms: int = 300
    input_device: int | str | None = None
    output_device: int | str | None = None
    playback_backend: str = "system"
    system_player: str = "auto"


class STTConfig(BaseModel):
    backend: str = "faster-whisper"
    model: str = "small"
    language: str = "pt"
    device: str = "auto"
    compute_type: str = "default"
    beam_size: int = 5
    cpu_threads: int = 0
    num_workers: int = 1
    fallback_to_cpu: bool = True
    cpu_fallback_compute_type: str = "int8"
    initial_prompt: str | None = (
        "Transcrição em português brasileiro (pt-BR), com ortografia do Brasil. "
        "Preserve nomes próprios e termos do Senac quando estiverem presentes."
    )


class TTSConfig(BaseModel):
    backend: str = "piper"
    executable: str = "piper"
    model: str = "models/tts/pt_BR-cadu-medium.onnx"
    config: str | None = "models/tts/pt_BR-cadu-medium.onnx.json"
    voice_repo: str = "rhasspy/piper-voices"
    voice_model_file: str = "pt/pt_BR/cadu/medium/pt_BR-cadu-medium.onnx"
    voice_config_file: str = "pt/pt_BR/cadu/medium/pt_BR-cadu-medium.onnx.json"
    voice_model_card_file: str = "pt/pt_BR/cadu/medium/MODEL_CARD"
    speaker: int | None = None
    length_scale: float = 1.0
    noise_scale: float = 0.667
    noise_w: float = 0.8


class LLMConfig(BaseModel):
    backend: str = "local-http"
    base_url: str = "http://127.0.0.1:8080/v1"
    model: str = "local-model"
    timeout_seconds: float = 45.0
    temperature: float = 0.1
    max_tokens: int = 180
    max_context_chars: int = 6_000


class AppConfig(BaseModel):
    name: str = "Orelhão IA"
    environment: str = "development"
    session_timeout_seconds: int = 120
    simulate_hardware: bool = True
    audio: AudioConfig = Field(default_factory=AudioConfig)
    stt: STTConfig = Field(default_factory=STTConfig)
    tts: TTSConfig = Field(default_factory=TTSConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)


def load_config(path: str | Path) -> AppConfig:
    file_path = Path(path)
    if not file_path.exists():
        return AppConfig()
    raw: dict[str, Any] = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
    return AppConfig.model_validate(raw)
