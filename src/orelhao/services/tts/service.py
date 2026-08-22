from typing import Protocol

from orelhao.interfaces.voice.audio import PCM16Audio


class TTSService(Protocol):
    def synthesize(self, text: str) -> PCM16Audio: ...


class MockTTSService:
    def synthesize(self, text: str) -> PCM16Audio:
        del text
        # 250 ms de silêncio: nesta versão o TTS real ainda não faz parte do escopo.
        return PCM16Audio(data=b"\x00\x00" * 4000, sample_rate=16_000, channels=1)
