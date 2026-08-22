from typing import Protocol

from orelhao.interfaces.voice.audio import PCM16Audio


class STTService(Protocol):
    def transcribe(self, audio: PCM16Audio) -> str: ...


class MockSTTService:
    def transcribe(self, audio: PCM16Audio) -> str:
        del audio
        return "Quais cursos de tecnologia o Senac oferece?"
