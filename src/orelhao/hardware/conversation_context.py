"""Memória curta e efêmera por ligação para resolver referências no RAG.

Nunca utiliza respostas anteriores como evidência factual. Apenas clarifica
a intenção/entidade da pergunta atual. Uma nova ligação cria uma instância nova.
"""
from __future__ import annotations

import re
import unicodedata
from collections import deque
from dataclasses import dataclass, field


def _normalize(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text.casefold())
    return re.sub(r"\s+", " ", "".join(c for c in plain if not unicodedata.combining(c))).strip()


@dataclass(frozen=True)
class ContextResolution:
    question: str
    query: str | None = None
    clarification: str | None = None
    reason: str | None = None

    @property
    def used_context(self) -> bool:
        return self.query is not None or self.clarification is not None

    @property
    def effective_question(self) -> str:
        return self.query or self.question


@dataclass(frozen=True)
class DialogueTurn:
    question: str
    answer: str
    topic: str | None
    entity: str | None


KNOWN_COURSES = (
    ("excel avançado", "Excel Avançado"),
    ("excel", "Excel"),
    ("técnico em desenvolvimento de sistemas", "Técnico em Desenvolvimento de Sistemas"),
    ("técnico em informática", "Técnico em Informática"),
    ("informática básica", "Informática Básica"),
)


@dataclass
class ConversationContext:
    """Retém no máximo quatro interações apenas na RAM do worker."""

    history: deque[DialogueTurn] = field(default_factory=lambda: deque(maxlen=4))
    topic: str | None = None
    entity: str | None = None

    def _entity_from_question(self, text: str) -> str | None:
        low = _normalize(text)
        for needle, label in KNOWN_COURSES:
            key = _normalize(needle)
            if re.search(rf"(?<!\w){re.escape(key)}(?!\w)", low):
                return label
        return None

    @staticmethod
    def _topic_from_question(text: str) -> str | None:
        low = _normalize(text)
        if re.search(r"\b(cursos?|capacitacao|formacao|gestao|comercio|comercial|"
                     r"tecnologia|idiomas?|excel|informatica|gastronomia)\b", low):
            return "cursos"
        if re.search(r"\b(unidades?|enderecos?|localizacao|mais proxima|mais proximo)\b", low):
            return "unidades"
        if re.search(r"\b(psg|gratuidade|bolsas?|gratuitos?)\b", low):
            return "gratuidade"
        return None

    def remember(self, question: str, answer: str = "", *, reset_topic: bool = False) -> None:
        """Memória de diálogo, não corpus, não log e não prova para o verificador."""
        if reset_topic:
            self.topic = None
            self.entity = None
        topic = self._topic_from_question(question)
        entity = self._entity_from_question(question)
        if topic:
            if topic != self.topic:
                self.entity = None
            self.topic = topic
        if entity:
            self.entity = entity
            self.topic = "cursos"
        self.history.append(DialogueTurn(
            question=question[:300],
            answer=answer[:300],
            topic=self.topic,
            entity=self.entity,
        ))

    def resolve(self, question: str) -> ContextResolution:
        original = question.strip()
        low = _normalize(original)
        if not original or not self.history:
            return ContextResolution(question=original)

        current_topic = self._topic_from_question(original)
        current_entity = self._entity_from_question(original)
        if current_topic is not None and current_topic != self.topic:
            return ContextResolution(question=original)

        # Não substituir uma nova entidade explícita pela entidade anterior.
        if current_entity and current_entity != self.entity:
            return ContextResolution(question=original)

        is_detail = bool(re.search(
            r"\b(preco|valor|custa|custo|quanto|carga horaria|duracao|requisitos?|"
            r"inscricao|matricula|vagas?|horarios?)\b", low
        ))
        is_followup = bool(re.match(
            r"^(e |entao |mas |qual |quais |quanto |quanto tempo |"
            r"e quanto |e qual |e quais |desses? |dessas? |dele |dela )",
            low,
        )) or bool(re.search(r"\b(desse|dessa|dele|dela|o mesmo|a mesma|nesse|nessa)\b", low))

        # Pergunta específica sem objeto: não adivinhar o curso.
        if (
            self.topic == "cursos" and is_detail and is_followup
            and self.entity is None and not current_entity
            and not re.search(
                r"\b(qual curso|quais cursos|curso de|curso do|"
                r"curso da|excel|informatica)\b", low
            )
        ):
            return ContextResolution(
                question=original,
                clarification="Qual curso do Senac você quer consultar?",
                reason="missing_course_entity",
            )

        if (
            self.topic == "cursos" and self.entity is not None
            and is_detail and is_followup and not current_entity
        ):
            return ContextResolution(
                question=original,
                query=f"{original.rstrip(' ?.!')} do curso {self.entity} no Senac Piauí?",
                reason="course_entity",
            )

        if self.topic == "cursos" and is_followup and not re.search(r"\bsenac\b", low):
            # Referência ao Senac é escopo de busca, não evidência do conteúdo.
            return ContextResolution(
                question=original,
                query=f"{original.rstrip(' ?.!')} no contexto de cursos do Senac Piauí?",
                reason="institution_scope",
            )

        if self.topic == "unidades" and is_followup and not re.search(r"\bsenac\b", low):
            return ContextResolution(
                question=original,
                query=f"{original.rstrip(' ?.!')} das unidades do Senac Piauí?",
                reason="units_scope",
            )

        if self.topic == "gratuidade" and is_followup and not re.search(r"\bpsg\b", low):
            return ContextResolution(
                question=original,
                query=f"{original.rstrip(' ?.!')} do Programa Senac de Gratuidade no Piauí?",
                reason="psg_scope",
            )
        return ContextResolution(question=original)
