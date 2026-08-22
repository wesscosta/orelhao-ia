from orelhao.interfaces.voice.capture import MockAudioCapture
from orelhao.services.llm.service import MockLLMService
from orelhao.services.rag.retriever import MockRetriever
from orelhao.services.stt.service import MockSTTService


def test_mock_pipeline_returns_grounded_answer() -> None:
    audio = MockAudioCapture().capture()
    query = MockSTTService().transcribe(audio)
    context = MockRetriever().search(query)
    answer = MockLLMService().generate(query, context)
    assert "base-senac-mock" in answer
