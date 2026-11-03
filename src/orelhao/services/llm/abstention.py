"""Normalização conservadora de recusas de evidência para o contrato do RAG.

Somente mensagens cujo conteúdo integral expressa ausência de evidência
são convertidas para o sentinel; mensagens mistas seguem para o grounding.
"""
from __future__ import annotations

import re

INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"

_EVIDENCE_TERMS = re.compile(
    r"\b(?:evid[eê]ncias?|contexto|fontes?|documentos?|trechos?|base de conhecimento)\b",
    re.IGNORECASE,
)
_ABSENCE_TERMS = re.compile(
    r"\b(?:n[aã]o\s+(?:[eé]\s+)?(?:foi\s+|est[aá]\s+)?"
    r"(?:informad[oa]s?|especificad[oa]s?|mencionad[oa]s?|"
    r"dispon[ií]ve(?:l|is)|encontrad[oa]s?|consta|constam|h[aá])"
    r"|aus[eê]ncia\s+de\s+(?:dados|informa[cç][oõ]es)|"
    r"(?:faltam|faltou)\s+(?:dados|informa[cç][oõ]es))\b",
    re.IGNORECASE,
)
# Impede transformar uma resposta que mistura recusa e informações concretas.
_MULTIPLE_SENTENCES = re.compile(r"[.!?]\s+\S")


def normalize_abstention(text: str) -> str:
    """Reconhece declarações curtas de ausência de evidência, sem inferir fatos."""
    answer = text.strip()
    # Modelos pequenos podem acrescentar pontuação ou repetir apenas o sentinel.
    # A saída inteira deve consistir somente no marcador, sem fatos misturados.
    if re.fullmatch(
        r"(?:INSUFFICIENT[\s_]+CONTEXT[.!]?\s*)+(?:INSUFFICIENT)?",
        answer, re.IGNORECASE,
    ):
        return INSUFFICIENT_CONTEXT
    if (
        len(answer) <= 240
        and not _MULTIPLE_SENTENCES.search(answer)
        and not re.search(r"\b(?:mas|por[eé]m|entretanto|contudo)\b", answer, re.IGNORECASE)
        and _EVIDENCE_TERMS.search(answer)
        and _ABSENCE_TERMS.search(answer)
    ):
        return INSUFFICIENT_CONTEXT
    return answer
