from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import ClassVar, Protocol

from orelhao.runtime_paths import resolve_project_path

from .evidence import (
    EvidenceVerifier,
    OnnxNliEvidenceVerifier,
    evidence_model_directory,
)
from .grounding_decision import GroundingDecision, GroundingPolicy
from .models import SearchResult
from .retriever import Retriever
from .vector_retriever import PersistentVectorRetriever


class AnswerGenerator(Protocol):
    def generate(self, question: str, evidence: list[SearchResult]) -> str: ...


class ExtractivePreviewAnswerGenerator:
    """Fallback determinístico até existir um backend LLM local de produção."""

    def generate(self, question: str, evidence: list[SearchResult]) -> str:
        del question
        if not evidence:
            return "Não encontrei evidência suficiente na base local para responder."
        return evidence[0].chunk.text.strip()


@dataclass(frozen=True, slots=True)
class ObservedEvidence:
    chunk_id: str
    source: str
    score: float
    text: str
    metadata: dict[str, str]


@dataclass(frozen=True, slots=True)
class ObservationLatency:
    retrieval_ms: float
    generation_ms: float
    grounding_ms: float
    total_ms: float


@dataclass(frozen=True, slots=True)
class GroundingObservation:
    observation_id: str
    created_at: str
    question: str
    answer: str
    presented_answer: str
    evidence: tuple[ObservedEvidence, ...]
    grounding: GroundingDecision
    latency: ObservationLatency
    mode: str = "observe"

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = asdict(self)
        payload["grounding"] = self.grounding.as_dict()
        return payload


class ObservationLog:
    """JSONL append-only; avaliações humanas não sobrescrevem a observação."""

    _RATINGS: ClassVar[set[str]] = {"correct", "partial", "incorrect"}

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def append_observation(self, observation: GroundingObservation) -> None:
        self._append({"event": "observation", **observation.as_dict()})

    def append_rating(
        self,
        observation_id: str,
        rating: str,
        *,
        grounding_status: str | None = None,
    ) -> str | None:
        if rating not in self._RATINGS:
            raise ValueError("avaliação deve ser correct, partial ou incorrect")
        if not observation_id.strip():
            raise ValueError("observation_id não pode ser vazio")
        diagnostic = _rating_diagnostic(rating, grounding_status)
        self._append(
            {
                "event": "human_rating",
                "observation_id": observation_id,
                "rating": rating,
                "grounding_status": grounding_status,
                "diagnostic": diagnostic,
                "created_at": datetime.now(UTC).isoformat(),
            }
        )
        return diagnostic

    def _append(self, payload: dict[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
        with self._lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(line)


class ObservationWorkbench:
    def __init__(
        self,
        retriever: Retriever,
        answer_generator: AnswerGenerator,
        verifier: EvidenceVerifier,
        log: ObservationLog,
        *,
        policy: GroundingPolicy | None = None,
    ) -> None:
        self._retriever = retriever
        self._answer_generator = answer_generator
        self._verifier = verifier
        self.log = log
        self._policy = policy or GroundingPolicy()

    def observe(self, question: str, *, limit: int = 4) -> GroundingObservation:
        clean_question = question.strip()
        if not clean_question:
            raise ValueError("pergunta não pode ser vazia")
        if limit <= 0:
            raise ValueError("limit deve ser maior que zero")

        total_started = perf_counter()
        started = perf_counter()
        results = self._retriever.search(clean_question, limit=limit)
        retrieval_ms = _elapsed_ms(started)

        started = perf_counter()
        answer = self._answer_generator.generate(clean_question, results).strip()
        generation_ms = _elapsed_ms(started)
        if not answer:
            raise RuntimeError("gerador produziu resposta vazia")

        passage = "\n\n".join(result.chunk.text for result in results)
        started = perf_counter()
        support = self._verifier.support_score(answer, passage) if passage else 0.0
        grounding_ms = _elapsed_ms(started)
        decision = self._policy.decide(support)

        observation = GroundingObservation(
            observation_id=uuid.uuid4().hex,
            created_at=datetime.now(UTC).isoformat(),
            question=clean_question,
            answer=answer,
            presented_answer=answer,
            evidence=tuple(
                ObservedEvidence(
                    chunk_id=result.chunk.id,
                    source=result.chunk.source,
                    score=result.score,
                    text=result.chunk.text,
                    metadata=dict(result.chunk.metadata),
                )
                for result in results
            ),
            grounding=decision,
            latency=ObservationLatency(
                retrieval_ms=retrieval_ms,
                generation_ms=generation_ms,
                grounding_ms=grounding_ms,
                total_ms=_elapsed_ms(total_started),
            ),
        )
        self.log.append_observation(observation)
        return observation


def build_default_observation_workbench(
    index_dir: Path,
    *,
    log_path: Path | None = None,
) -> ObservationWorkbench:
    model_dir = resolve_project_path(
        f"models/evidence/{evidence_model_directory('nli-minilm')}"
    )
    return ObservationWorkbench(
        PersistentVectorRetriever(index_dir),
        ExtractivePreviewAnswerGenerator(),
        OnnxNliEvidenceVerifier(model_dir),
        ObservationLog(log_path or index_dir.parent / "observations" / "grounding.jsonl"),
    )


def _elapsed_ms(started: float) -> float:
    return (perf_counter() - started) * 1000.0


def _rating_diagnostic(rating: str, grounding_status: str | None) -> str | None:
    if grounding_status is None:
        return None
    if grounding_status not in {"supported", "unsupported", "uncertain"}:
        raise ValueError("grounding_status inválido")
    if rating == "correct" and grounding_status != "supported":
        return "possible_false_negative"
    if rating != "correct" and grounding_status == "supported":
        return "possible_false_positive"
    return "aligned"
