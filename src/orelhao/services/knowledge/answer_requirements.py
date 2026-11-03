"""Verifica se a resposta apresenta o *tipo* de dado solicitado.

O NLI pode confirmar uma frase verdadeira, mas irrelevante para o atributo
pedido (ex.: "quem pode entrar" em resposta a "qual a lotação máxima").
A detecção é fechada: só atua em perguntas com marcadores explícitos.
"""
from __future__ import annotations

import re

from .fact_extraction import FactKind, extract_explicit_facts, normalize

_REQUIREMENTS: tuple[tuple[str, frozenset[FactKind]], ...] = (
    (r"\b(?:lotacao|capacidade)\s+(?:maxima|total|do|da)\b",
     frozenset({FactKind.CAPACITY})),
    (r"\b(?:quantas?\s+horas|carga\s+horaria|duracao\s+do\s+curso)\b",
     frozenset({FactKind.DURATION})),
    (r"\b(?:faixa\s+etaria|intervalo\s+de\s+idade)\b",
     frozenset({FactKind.AGE_RANGE})),
    (r"\b(?:idade\s+minima|quantos?\s+anos\s+(?:de\s+idade|para))\b",
     frozenset({FactKind.AGE})),
    (r"\b(?:qual\s+(?:o\s+)?(?:valor|preco)|quanto\s+custa|mensalidade)\b",
     frozenset({FactKind.PRICE})),
    (r"\b(?:qual\s+(?:o\s+)?(?:telefone|numero\s+de\s+contato))\b",
     frozenset({FactKind.PHONE})),
    (r"\b(?:quantas?\s+vagas|quantitativo\s+(?:previsto|de\s+vagas))\b",
     frozenset({FactKind.VACANCIES})),
    (r"\b(?:qual\s+(?:e\s+)?(?:o\s+)?prazo\s+de\s+resposta)\b",
     frozenset({FactKind.DEADLINE})),
)


def required_fact_kinds(question: str) -> frozenset[FactKind]:
    text = normalize(question)
    return next(
        (kinds for pattern, kinds in _REQUIREMENTS if re.search(pattern, text)),
        frozenset(),
    )


def missing_requested_fact(question: str, answer: str) -> bool:
    """Não há aprovação positiva: somente indicação de atributo não respondido."""
    required = required_fact_kinds(question)
    if not required:
        return False
    return not any(fact.kind in required for fact in extract_explicit_facts(answer))
