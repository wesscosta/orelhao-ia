from __future__ import annotations

import json
import os
import re
import threading
import unicodedata
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import ClassVar, Protocol
from zoneinfo import ZoneInfo

from orelhao.runtime_paths import resolve_project_path
from orelhao.services.llm.service import INSUFFICIENT_CONTEXT, LLMService
from orelhao.services.rag.retriever import RetrievedContext

from .answerability import EvidenceAdjudicator, EvidenceAssessment
from .claim_grounding import ClaimAssessment, assess_answer
from .evidence import (
    EvidenceVerifier,
    OnnxNliEvidenceVerifier,
    evidence_model_directory,
)
from .grounding_decision import GroundingDecision, GroundingPolicy
from .models import SearchResult
from .query_constraints import explicitly_named_entities
from .retriever import Retriever
from .vector_retriever import PersistentVectorRetriever


class AnswerGenerator(Protocol):
    def generate(self, question: str, evidence: list[SearchResult]) -> str: ...


class ExtractivePreviewAnswerGenerator:
    """Fallback determinístico até existir um backend LLM local de produção."""

    def generate(self, question: str, evidence: list[SearchResult]) -> str:
        if not evidence:
            return "Não encontrei evidência suficiente na base local para responder."
        candidates: list[tuple[float, int, str]] = []
        question_terms = _meaningful_terms(question)
        location_intent = bool(question_terms & {"onde", "endereco", "localizacao", "fica"})
        for result_index, result in enumerate(evidence):
            clean = _plain_text(result.chunk.text)
            for sentence in _sentences(clean):
                sentence_terms = _meaningful_terms(sentence)
                overlap = len(question_terms & sentence_terms)
                coverage = overlap / max(1, len(question_terms))
                location_signal = bool(
                    sentence_terms
                    & {"endereco", "localizacao", "unidade", "cidade", "municipio", "funcionamento"}
                )
                score = coverage + result.score * 0.25
                if location_intent and location_signal:
                    score += 0.35
                candidates.append((score, -result_index, sentence))
        if not candidates:
            return "Não encontrei evidência suficiente na base local para responder."
        candidates.sort(reverse=True)
        selected: list[str] = []
        total = 0
        for _, _, sentence in candidates:
            if sentence in selected or total + len(sentence) > 360:
                continue
            selected.append(sentence)
            total += len(sentence)
            if len(selected) == 2:
                break
        return " ".join(selected)


GENERATION_ABSTENTION_MESSAGE = (
    "Não encontrei evidências suficientes na base de conhecimento para responder com segurança."
)


class LocalLLMAnswerGenerator:
    def __init__(self, service: LLMService) -> None:
        self._service = service

    def generate(self, question: str, evidence: list[SearchResult]) -> str:
        context = [
            RetrievedContext(text=result.chunk.text, source=result.chunk.source)
            for result in evidence
        ]
        answer = self._service.generate(question, context).strip()
        if answer == INSUFFICIENT_CONTEXT:
            return GENERATION_ABSTENTION_MESSAGE
        clean = _plain_text(answer)
        if not clean:
            raise RuntimeError("LLM local produziu resposta vazia após normalização")
        sentences = _sentences(clean)
        if len(sentences) > 1 and not sentences[-1].endswith((".", "!", "?")):
            # A saída pode ter sido interrompida pelo limite de tokens.
            sentences.pop()
        selected: list[str] = []
        for sentence in sentences[:3]:
            proposed = " ".join([*selected, sentence])
            if len(proposed) > 360:
                break
            selected.append(sentence)
        return " ".join(selected) if selected else GENERATION_ABSTENTION_MESSAGE


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
    adjudication_ms: float = 0.0


@dataclass(frozen=True, slots=True)
class GroundingObservation:
    observation_id: str
    created_at: str
    question: str
    answer: str
    presented_answer: str
    evidence: tuple[ObservedEvidence, ...]
    grounding: GroundingDecision
    claims: tuple[ClaimAssessment, ...]
    latency: ObservationLatency
    generator: str
    generation_abstained: bool
    mode: str = "observe"
    answerability: EvidenceAssessment | None = None
    generation_skipped: bool = False
    answer_entity_mismatch: bool = False

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = asdict(self)
        payload["grounding"] = self.grounding.as_dict()
        if self.answerability is not None:
            payload["answerability"] = self.answerability.as_dict()
        return payload


class ObservationLog:
    """JSONL append-only; avaliações humanas não sobrescrevem a observação."""

    _RATINGS: ClassVar[set[str]] = {"correct", "partial", "incorrect"}

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def append_observation(self, observation: GroundingObservation) -> None:
        self._append({"event": "observation", **observation.as_dict()})

    def presented_answer_for(self, observation_id: str) -> str | None:
        """Resolve áudio somente de uma observação legítima já registrada."""
        if re.fullmatch(r"[0-9a-f]{32}", observation_id) is None:
            return None
        try:
            with self.path.open(encoding="utf-8") as stream:
                for line in stream:
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if (
                        payload.get("event") == "observation"
                        and payload.get("observation_id") == observation_id
                    ):
                        answer = payload.get("presented_answer")
                        return answer if isinstance(answer, str) and answer else None
        except FileNotFoundError:
            return None
        return None

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
        mode: str = "observe",
        adjudicator: EvidenceAdjudicator | None = None,
    ) -> None:
        if mode not in {"observe", "enforce"}:
            raise ValueError("mode deve ser observe ou enforce")
        self._mode = mode
        self._retriever = retriever
        self._answer_generator = answer_generator
        self._verifier = verifier
        self.log = log
        self._policy = policy or GroundingPolicy()
        self._adjudicator = adjudicator

    def observe(
        self, question: str, *, limit: int = 8, mode: str | None = None
    ) -> GroundingObservation:
        effective_mode = mode or self._mode
        if effective_mode not in {"observe", "enforce"}:
            raise ValueError("mode deve ser observe ou enforce")
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
        precheck = (
            self._adjudicator.assess(clean_question, results, as_of=datetime.now(
                ZoneInfo(os.getenv("ORELHAO_TIMEZONE", "America/Fortaleza"))
            ).date())
            if self._adjudicator is not None else None
        )
        adjudication_ms = _elapsed_ms(started)
        blocked_before_generation = bool(
            precheck is not None and not precheck.decision.answerable
            and effective_mode == "enforce"
        )

        started = perf_counter()
        if blocked_before_generation:
            assert precheck is not None
            answer = precheck.decision.message_pt_br() or GENERATION_ABSTENTION_MESSAGE
        else:
            eligible = (
                [r for r in results if r.chunk.id in precheck.admissible_chunk_ids]
                if precheck is not None and precheck.decision.answerable
                and effective_mode == "enforce" else results
            )
            answer = self._answer_generator.generate(clean_question, eligible).strip()
        generation_ms = _elapsed_ms(started)
        if not answer:
            raise RuntimeError("gerador produziu resposta vazia")

        generation_abstained = blocked_before_generation or answer == GENERATION_ABSTENTION_MESSAGE
        started = perf_counter()
        eligible_evidence = (
            [r for r in results if r.chunk.id in precheck.admissible_chunk_ids]
            if precheck is not None and precheck.decision.answerable else results
        )
        assessment = (
            assess_answer("", eligible_evidence, self._verifier, self._policy)
            if generation_abstained
            else assess_answer(answer, eligible_evidence, self._verifier, self._policy)
        )
        grounding_ms = _elapsed_ms(started)
        decision = assessment.decision
        answer_entities = explicitly_named_entities(
            answer,
            [
                str(result.chunk.metadata["entity_id"])
                for result in results
                if result.chunk.metadata.get("entity_id")
            ],
        )
        answer_entity_mismatch = bool(
            precheck is not None and precheck.constraints.entity_id
            and any(entity != precheck.constraints.entity_id for entity in answer_entities)
        )
        if answer_entity_mismatch:
            decision = self._policy.decide(0.0)
        presented = (
            GENERATION_ABSTENTION_MESSAGE
            if effective_mode == "enforce" and (
                decision.should_abstain or answer_entity_mismatch or (
                    precheck is not None and not precheck.decision.answerable
                )
            ) and not blocked_before_generation
            else answer
        )

        observation = GroundingObservation(
            observation_id=uuid.uuid4().hex,
            created_at=datetime.now(UTC).isoformat(),
            question=clean_question,
            answer=answer,
            presented_answer=presented,
            claims=assessment.claims,
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
                adjudication_ms=adjudication_ms,
            ),
            generator=type(self._answer_generator).__name__,
            generation_abstained=generation_abstained,
            mode=effective_mode,
            answerability=precheck,
            generation_skipped=blocked_before_generation,
            answer_entity_mismatch=answer_entity_mismatch,
        )
        self.log.append_observation(observation)
        return observation


def build_default_observation_workbench(
    index_dir: Path,
    *,
    log_path: Path | None = None,
    answer_generator: AnswerGenerator | None = None,
    mode: str = "observe",
) -> ObservationWorkbench:
    model_dir = resolve_project_path(
        f"models/evidence/{evidence_model_directory('nli-minilm')}"
    )
    return ObservationWorkbench(
        PersistentVectorRetriever(index_dir),
        answer_generator or ExtractivePreviewAnswerGenerator(),
        OnnxNliEvidenceVerifier(model_dir),
        ObservationLog(log_path or index_dir.parent / "observations" / "grounding.jsonl"),
        mode=mode,
        adjudicator=EvidenceAdjudicator(),
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


def _plain_text(value: str) -> str:
    text = re.sub(r"```.*?```", " ", value, flags=re.DOTALL)
    text = re.sub(r"^\s*#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\[([^]]+)]\([^)]+\)", r"\1", text)
    text = re.sub(r"[*_`>|]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _sentences(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", value) if part.strip()]


def _meaningful_terms(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    plain = "".join(char for char in normalized if not unicodedata.combining(char))
    stopwords = {
        "a", "as", "de", "do", "dos", "e", "em", "no", "nos", "o", "os", "para", "por",
        "qual", "que", "tem", "um", "uma",
    }
    return {
        term for term in re.findall(r"[a-z0-9]+", plain) if len(term) >= 2 and term not in stopwords
    }
