from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from orelhao.config import LLMConfig
from orelhao.services.rag.retriever import RetrievedContext

from .prompts import SYSTEM_PROMPT

INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"


class LLMProtocolError(RuntimeError):
    pass


class LLMService(Protocol):
    def generate(self, query: str, context: list[RetrievedContext]) -> str: ...


class MockLLMService:
    def generate(self, query: str, context: list[RetrievedContext]) -> str:
        source = context[0].source if context else "sem fonte"
        return f"Resposta simulada para '{query}'. A resposta foi baseada na fonte {source}."


@dataclass(frozen=True, slots=True)
class LLMHealth:
    available: bool
    detail: str


class LocalOpenAICompatibleLLMService:
    """Cliente para servidor de inferência estritamente local compatível com OpenAI."""

    def __init__(self, config: LLMConfig) -> None:
        if config.backend != "local-http":
            raise ValueError("backend LLM deve ser local-http")
        parsed = urlsplit(config.base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("base_url da LLM deve usar HTTP em loopback")
        if not 0.0 <= config.temperature <= 2.0:
            raise ValueError("temperature da LLM deve estar entre 0 e 2")
        if config.timeout_seconds <= 0 or config.max_tokens <= 0 or config.max_context_chars <= 0:
            raise ValueError("limites da LLM devem ser positivos")
        self.config = config
        self.base_url = config.base_url.rstrip("/")

    def health(self) -> LLMHealth:
        try:
            readiness = self._request("GET", "/health", timeout_seconds=2.0)
            if readiness.get("status") != "ok":
                return LLMHealth(False, "servidor local ainda está carregando o modelo")
            payload = self._request("GET", "/models", timeout_seconds=2.0)
        except RuntimeError as exc:
            return LLMHealth(False, str(exc))
        models = payload.get("data")
        if not isinstance(models, list):
            return LLMHealth(False, "servidor local não informou modelos")
        model_ids = {
            item.get("id") for item in models if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        if self.config.model not in model_ids:
            return LLMHealth(
                False,
                f"modelo configurado {self.config.model!r} não está disponível",
            )
        return LLMHealth(True, f"modelo {self.config.model!r} disponível")

    def generate(self, query: str, context: list[RetrievedContext]) -> str:
        clean_query = query.strip()
        if not clean_query:
            raise ValueError("pergunta para LLM não pode ser vazia")
        if not context:
            return INSUFFICIENT_CONTEXT
        evidence = self._format_context(context)
        payload = self._request(
            "POST",
            "/chat/completions",
            {
                "model": self.config.model,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"EVIDÊNCIAS:\n{evidence}\n\nPERGUNTA:\n{clean_query}",
                    },
                ],
            },
        )
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise LLMProtocolError("resposta da LLM local possui choices inválido")
        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise LLMProtocolError("resposta da LLM local possui message inválido")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("LLM local produziu resposta vazia")
        return content.strip()

    def _format_context(self, context: list[RetrievedContext]) -> str:
        sections: list[str] = []
        used = 0
        for index, item in enumerate(context, start=1):
            section = f"[EVIDÊNCIA {index} — {item.source}]\n{item.text.strip()}"
            remaining = self.config.max_context_chars - used
            if remaining <= 0:
                break
            section = section[:remaining]
            sections.append(section)
            used += len(section) + 2
        return "\n\n".join(sections)

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
        *,
        timeout_seconds: float | None = None,
    ) -> dict[str, object]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(
                request,
                timeout=timeout_seconds or self.config.timeout_seconds,
            ) as response:
                raw = response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise RuntimeError(f"LLM local respondeu HTTP {exc.code}: {detail}") from exc
        except (TimeoutError, URLError) as exc:
            raise RuntimeError(f"LLM local indisponível em {self.base_url}: {exc}") from exc
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("LLM local retornou JSON inválido") from exc
        if not isinstance(decoded, dict):
            raise LLMProtocolError("LLM local retornou payload inválido")
        return decoded
