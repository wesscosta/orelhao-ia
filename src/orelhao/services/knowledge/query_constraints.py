"""Extrai restrições explícitas para validação pré-geração (não é NER livre)."""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date


def normalize(value: str) -> str:
    plain = unicodedata.normalize("NFKD", value.casefold())
    return re.sub(r"\s+", " ", "".join(c for c in plain if not unicodedata.combining(c))).strip()


@dataclass(frozen=True, slots=True)
class QueryConstraints:
    entity_id: str | None = None
    unit_id: str | None = None
    attribute: str | None = None
    requires_current_state: bool = False
    reference_date: date | None = None


_ATTRIBUTE_PATTERNS = (
    ("availability", r"\b(?:vaga|vagas|inscri(?:cao|coes)|matricula|matriculas|disponib\w*|abert\w*)\b"),
    ("schedule", r"\b(?:horario|horarios|atendimento|funcionamento|turno|turnos)\b"),
    ("price", r"\b(?:preco|valor|custa|custo|mensalidade|taxa)\b"),
    ("contact", r"\b(?:telefone|whatsapp|contato|email)\b"),
    ("address", r"\b(?:endereco|rua|avenida|localizacao|onde fica)\b"),
    ("duration", r"\b(?:carga horaria|quantas horas|duracao)\b"),
)
_CURRENT = re.compile(r"\b(?:hoje|agora|atualmente|atual|vigente|ainda|neste momento|em aberto|disponiveis? agora)\b")
_UNIT = re.compile(r"\bunidade(?: do senac)?\s+(?:de|do|da|em)\s+([\w\s-]{2,45})")
_COURSE = re.compile(r"\bcurso\s+(?:de|do|da)\s+([\w\s-]{2,45})")


def _extract(match: re.Match[str] | None) -> str | None:
    if match is None:
        return None
    text = re.split(
        r"\b(?:hoje|agora|atualmente|ainda|com|que|qual|para|no|na|em)\b",
        match.group(1),
    )[0].strip(" ?.!,")
    return text or None


def explicitly_named_entities(question: str, known_entities: Iterable[str]) -> tuple[str, ...]:
    """Identifica nomes completos de entidades versionadas, sem cascatear subtipos.

    Ex.: pergunta "Excel Avançado" não equivale à entidade "Excel".
    Consultas comparativas envolvendo várias entidades permanecem multiescopo.
    """
    normalized = normalize(question)
    candidates: list[tuple[int, int, str]] = []
    for identity in set(known_entities):
        if ":" not in identity:
            continue
        _, label = identity.split(":", 1)
        label = normalize(label)
        if not label:
            continue
        for match in re.finditer(r"(?<!\w)" + re.escape(label) + r"(?!\w)", normalized):
            candidates.append((match.start(), match.end(), identity))
    occupied: list[tuple[int, int]] = []
    selected: set[str] = set()
    for start, end, entity in sorted(candidates, key=lambda v: (-(v[1]-v[0]), v[0])):
        if any(start < right and end > left for left, right in occupied):
            continue
        occupied.append((start, end))
        selected.add(entity)
    return tuple(sorted(selected))


def parse_query_constraints(
    question: str, *, as_of: date, known_entities: Iterable[str] = (),
) -> QueryConstraints:
    text = normalize(question)
    attribute = next((name for name, pattern in _ATTRIBUTE_PATTERNS if re.search(pattern, text)), None)
    current = bool(_CURRENT.search(text)) or (
        attribute == "availability" and bool(re.search(r"\b(?:abert\w*|disponiveis?)\b", text))
    )
    unit = _extract(_UNIT.search(text))
    course = _extract(_COURSE.search(text))
    matched = explicitly_named_entities(question, known_entities)
    entity_id = (
        matched[0] if len(matched) == 1
        else (None if len(matched) > 1 else (f"curso:{course}" if course else None))
    )
    return QueryConstraints(
        entity_id=entity_id,
        unit_id=unit,
        attribute=attribute,
        requires_current_state=current,
        reference_date=as_of if current else None,
    )
