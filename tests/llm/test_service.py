import json
from typing import Any, Self

import pytest

from orelhao.config import LLMConfig
from orelhao.services.llm import service as service_module
from orelhao.services.llm.service import LocalOpenAICompatibleLLMService
from orelhao.services.rag.retriever import RetrievedContext


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


def test_local_llm_sends_grounded_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(request: Any, timeout: float) -> FakeResponse:
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data)
        return FakeResponse(
            {"choices": [{"message": {"content": "O atendimento ocorre de segunda a sexta."}}]}
        )

    monkeypatch.setattr(service_module, "urlopen", fake_urlopen)
    service = LocalOpenAICompatibleLLMService(LLMConfig(model="teste-local"))

    answer = service.generate(
        "Quando ocorre o atendimento?",
        [RetrievedContext("Atendimento de segunda a sexta.", "faq.md")],
    )

    assert answer == "O atendimento ocorre de segunda a sexta."
    assert captured["url"] == "http://127.0.0.1:8080/v1/chat/completions"
    payload = captured["payload"]
    assert payload["model"] == "teste-local"
    assert "INSUFFICIENT_CONTEXT" in payload["messages"][0]["content"]
    assert "faq.md" in payload["messages"][1]["content"]


def test_local_llm_rejects_non_loopback_url() -> None:
    with pytest.raises(ValueError, match="loopback"):
        LocalOpenAICompatibleLLMService(
            LLMConfig(base_url="https://api.example.com/v1")
        )


def test_local_llm_health_reports_models(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_health(request: Any, timeout: float) -> FakeResponse:
        if request.full_url.endswith("/health"):
            return FakeResponse({"status": "ok"})
        return FakeResponse({"data": [{"id": "local-model"}]})

    monkeypatch.setattr(
        service_module,
        "urlopen",
        fake_health,
    )
    health = LocalOpenAICompatibleLLMService(LLMConfig()).health()

    assert health.available
    assert "local-model" in health.detail


def test_llm_health_uses_root_health_route(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_urlopen(request: Any, timeout: float) -> FakeResponse:
        del timeout
        calls.append(request.full_url)
        if request.full_url.endswith("/health"):
            return FakeResponse({"status": "ok"})
        return FakeResponse({"data": [{"id": "local-model"}]})

    monkeypatch.setattr(service_module, "urlopen", fake_urlopen)
    health = LocalOpenAICompatibleLLMService(LLMConfig()).health()
    assert health.available
    assert calls == ["http://127.0.0.1:8080/health", "http://127.0.0.1:8080/v1/models"]


def test_completion_preserves_server_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: Any, timeout: float) -> FakeResponse:
        del request, timeout
        return FakeResponse({
            "choices": [{"message": {"content": "O curso é gratuito."}}],
            "usage": {"prompt_tokens": 33, "completion_tokens": 7},
            "timings": {"predicted_per_second": 4.5},
        })

    monkeypatch.setattr(service_module, "urlopen", fake_urlopen)
    service = LocalOpenAICompatibleLLMService(LLMConfig())
    completion = service.generate_completion(
        "Qual é o valor?", [RetrievedContext("O curso é gratuito.", "curso.md")]
    )
    assert completion.prompt_tokens == 33
    assert completion.completion_tokens == 7
    assert completion.tokens_per_second == 4.5


def test_normalizes_llm_refusal_and_retains_original(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = "O valor não é especificado nas evidências fornecidas."

    def fake_urlopen(request: Any, timeout: float) -> FakeResponse:
        del request, timeout
        return FakeResponse({"choices": [{"message": {"content": raw}}]})

    monkeypatch.setattr(service_module, "urlopen", fake_urlopen)
    service = LocalOpenAICompatibleLLMService(LLMConfig())
    completion = service.generate_completion(
        "Qual é o preço?", [RetrievedContext("O curso tem quatro meses.", "curso.md")]
    )
    assert completion.text == "INSUFFICIENT_CONTEXT"
    assert completion.raw_text == raw



def test_lumi_uses_masculine_article_and_preserves_raw_llm_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from orelhao.services.llm.service import normalize_lumi_identity

    assert normalize_lumi_identity("Eu sou a Lumi, assistente virtual.") == (
        "Eu sou o Lumi, assistente virtual."
    )
    assert normalize_lumi_identity("A Lumi responde à Lumi.") == (
        "O Lumi responde ao Lumi."
    )
    assert normalize_lumi_identity("Os serviços da Lumi.") == "Os serviços do Lumi."
    assert normalize_lumi_identity("O Lumi está disponível.") == "O Lumi está disponível."
    assert normalize_lumi_identity("a luminosidade melhorou") == "a luminosidade melhorou"

    raw = "Olá! Eu sou a Lumi, assistente virtual."

    def fake_urlopen(request: Any, timeout: float) -> FakeResponse:
        del request, timeout
        return FakeResponse({"choices": [{"message": {"content": raw}}]})

    monkeypatch.setattr(service_module, "urlopen", fake_urlopen)
    service = LocalOpenAICompatibleLLMService(LLMConfig())
    completion = service.generate_completion(
        "Qual seu nome?", [RetrievedContext("Assistente.", "institucional.md")]
    )
    assert completion.text == "Olá! Eu sou o Lumi, assistente virtual."
    assert completion.raw_text == raw


def test_system_prompt_uses_lumi_masculine_identity() -> None:
    from orelhao.services.llm.prompts import SYSTEM_PROMPT

    assert '"o Lumi"' in SYSTEM_PROMPT
    assert '"sou o Lumi"' in SYSTEM_PROMPT
