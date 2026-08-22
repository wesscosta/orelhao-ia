from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import wave


@dataclass(frozen=True, slots=True)
class PCM16Audio:
    data: bytes
    sample_rate: int = 16_000
    channels: int = 1

    @property
    def sample_width(self) -> int:
        return 2

    @property
    def duration_seconds(self) -> float:
        frame_count = len(self.data) / (self.sample_width * self.channels)
        return frame_count / self.sample_rate

    def to_wav_bytes(self) -> bytes:
        buffer = BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(self.channels)
            wav.setsampwidth(self.sample_width)
            wav.setframerate(self.sample_rate)
            wav.writeframes(self.data)
        return buffer.getvalue()

    @classmethod
    def from_wav_bytes(cls, payload: bytes) -> "PCM16Audio":
        with wave.open(BytesIO(payload), "rb") as wav:
            if wav.getsampwidth() != 2:
                raise ValueError("Somente WAV PCM16 é suportado nesta etapa")
            return cls(
                data=wav.readframes(wav.getnframes()),
                sample_rate=wav.getframerate(),
                channels=wav.getnchannels(),
            )
