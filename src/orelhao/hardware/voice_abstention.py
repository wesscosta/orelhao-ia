"""Tom de voz quando não há evidência suficiente para responder.

A política é exclusivamente de apresentação para o monofone; não altera
retrieval, precheck, NLI, decisão V3 ou resposta bruta do workbench.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    return "".join(
        char for char in normalized if not unicodedata.combining(char)
    )


@dataclass
class VoiceAbstentionPolicy:
    """A brincadeira aparece no máximo uma vez por ligação."""

    refusals: int = 0

    def choose_prompt(self, question: str) -> str:
        text = _normalize(question)
        first = self.refusals == 0
        self.refusals += 1

        # Conteúdo operacional atual precisa ser encaminhado ao atendimento.
        if re.search(
            r"\b(?:vagas?|matriculas?|inscric(?:ao|oes)|precos?|valor(?:es)?|"
            r"quanto custa|turmas? abertas?|disponibilidade atual)\b",
            text,
        ):
            return "abstention_admissions"
        # Encaminhar à supervisão apenas assuntos de ensino/acompanhamento.
        if re.search(
            r"\b(?:avaliac(?:ao|oes)|frequencia|faltas?|reprovac(?:ao|oes)|"
            r"professores?|orientacao pedagogica|disciplina escolar)\b",
            text,
        ):
            return "abstention_pedagogy"
        return "abstention_humor" if first else "abstention_followup"
