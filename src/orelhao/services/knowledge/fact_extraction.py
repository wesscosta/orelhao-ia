"""Extrai valores factuais explícitos de texto em pt-BR (sem inferência semântica)."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum


def normalize(text: str) -> str:
    decomp = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in decomp if not unicodedata.combining(c))


class FactKind(StrEnum):
    PRICE = "price_brl"
    DURATION = "duration_hours"
    AGE = "minimum_age_years"
    AGE_RANGE = "age_range_years"
    DEADLINE = "deadline_days"
    VACANCIES = "vacancies"
    PHONE = "phone"
    DATE = "date"
    CAPACITY = "capacity"


@dataclass(frozen=True, slots=True)
class ExtractedFact:
    kind: FactKind
    value: str
    unit: str
    start: int
    end: int
    literal: str
    qualifier: str = "unspecified"
    reference_id: str | None = None

    def __post_init__(self) -> None:
        if self.start < 0 or self.end <= self.start or not self.value:
            raise ValueError("fato ou offsets inválidos")

    def as_dict(self) -> dict[str, str | int | None]:
        return {
            "kind": self.kind.value, "value": self.value, "unit": self.unit,
            "start": self.start, "end": self.end, "literal": self.literal,
            "qualifier": self.qualifier, "reference_id": self.reference_id,
        }


_PRICE = re.compile(r"R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2}|\d+)(?![\d,])", re.IGNORECASE)
_HOURS = re.compile(r"(?<![\w/])(\d{1,4})\s+horas?\b", re.IGNORECASE)
_AGE = re.compile(r"(?<!\d)(\d{1,3})\s+anos\b", re.IGNORECASE)
_AGE_RANGE = re.compile(
    r"(?<!\d)(\d{1,3})\s+(?:a|até|ate|-)\s+(\d{1,3})\s+anos\b",
    re.IGNORECASE,
)
_DAYS = re.compile(r"(?<!\d)(\d{1,4})\s+dias?\s*(úteis|uteis|corridos)?\b", re.IGNORECASE)
_VACANCIES = re.compile(r"(?<!\d)(\d{1,6})\s+vagas\b", re.IGNORECASE)
_CAPACITY = re.compile(
    r"(?<!\d)(\d{1,5})\s+(pessoas?|lugares?|assentos?|visitantes?)\b",
    re.IGNORECASE,
)
_PHONE = re.compile(r"(?<!\d)(?:\+55[\s-]*)?\(?\d{2}\)?[\s-]*\d{4,5}[\s-]*-?\d{4}(?!\d)")
_DATE = re.compile(r"(?<!\d)(?:\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})(?!\d)")
_REF = re.compile(r"(?<!\d)(\d{1,3}/20\d{2})(?!\d)")


def _line(text: str, position: int) -> str:
    start = text.rfind("\n", 0, position) + 1
    end = text.find("\n", position)
    return text[start:end if end >= 0 else len(text)]


def _reference(text: str, position: int) -> str | None:
    start = text.rfind("\n", 0, position) + 1
    matches = list(_REF.finditer(text, start, position))
    return matches[-1].group(1) if matches else None


def _date_value(value: str) -> str | None:
    try:
        if "/" in value:
            day, month, year = map(int, value.split("/"))
            return date(year, month, day).isoformat()
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None


def extract_explicit_facts(text: str) -> tuple[ExtractedFact, ...]:
    """Não infere valores implícitos; offsets sempre relativos ao texto informado."""
    facts: list[ExtractedFact] = []

    def add(
        match: re.Match[str], kind: FactKind, value: str, unit: str,
        qualifier: str = "unspecified", ref: str | None = None,
    ) -> None:
        facts.append(ExtractedFact(
            kind, value, unit, match.start(), match.end(), match.group(), qualifier, ref,
        ))

    for m in _PRICE.finditer(text):
        try:
            amount = Decimal(m.group(1).replace(".", "").replace(",", "."))
        except InvalidOperation:
            continue
        add(m, FactKind.PRICE, str(amount.quantize(Decimal("0.01"))), "BRL")
    for m in _HOURS.finditer(text):
        head = normalize(_line(text, m.start()).split(m.group(), 1)[0])
        if "prazo" in head and not any(k in head for k in ("curso", "carga", "turma")):
            continue
        add(m, FactKind.DURATION, str(int(m.group(1))), "hours")
    age_ranges: list[tuple[int, int]] = []
    for m in _AGE_RANGE.finditer(text):
        # "14 a 24 anos" já expressa explicitamente uma faixa etária, mesmo
        # quando uma resposta curta omite a palavra "idade".
        first, last = int(m.group(1)), int(m.group(2))
        if not 0 <= first <= last <= 120:
            continue
        add(m, FactKind.AGE_RANGE, f"{first}-{last}", "years_range", "range")
        age_ranges.append((m.start(), m.end()))
    for m in _AGE.finditer(text):
        if any(start <= m.start() < end for start, end in age_ranges):
            continue
        context = normalize(text[max(0, m.start() - 65):min(len(text), m.end() + 18)])
        if not re.search(r"\b(?:idade|etaria|minima|acesso|a partir|anos ou mais)\b", context):
            continue
        add(m, FactKind.AGE, str(int(m.group(1))), "years")
    for m in _DAYS.finditer(text):
        unit = normalize(m.group(2) or "")
        unit = {"uteis": "business_days", "corridos": "calendar_days"}.get(
            unit, "unspecified_days"
        )
        prefix = normalize(text[max(0, m.start() - 40):m.start()])
        role = "extension" if re.search(r"(?:prorrog\w*|mais|estend\w*)", prefix) else "base"
        add(m, FactKind.DEADLINE, str(int(m.group(1))), unit, role)
    for m in _VACANCIES.finditer(text):
        line = normalize(_line(text, m.start()))
        if re.search(r"\b(?:previst\w*|preve\w*|publicac\w*|quantitativo)\b", line):
            role = "published"
        elif re.search(r"\b(?:restant\w*|disponiveis|abertas|livres)\b", line):
            role = "available"
        else:
            role = "unspecified"
        add(
            m, FactKind.VACANCIES, str(int(m.group(1))), "vacancies",
            role, _reference(text, m.start()),
        )
    for m in _CAPACITY.finditer(text):
        # Não classificar um contador casual como lotação sem marcador de capacidade.
        ctx = normalize(_line(text, m.start()))
        if re.search(r"\b(?:lotac\w*|capacidade|comporta\w*|suporta\w*)\b", ctx):
            add(m, FactKind.CAPACITY, str(int(m.group(1))), "persons")
    for m in _PHONE.finditer(text):
        # Uma sequência nua de 11 dígitos pode ser CPF, não telefone.
        if re.fullmatch(r"\d{10,11}", m.group()) and not re.search(
            r"\b(?:telefone|contato|whatsapp|fone)\b",
            normalize(_line(text, m.start())),
        ):
            continue
        digits = re.sub(r"\D", "", m.group())
        if len(digits) in (12, 13) and digits.startswith("55"):
            digits = digits[2:]
        if len(digits) in (10, 11):
            add(m, FactKind.PHONE, digits, "br_phone")
    for m in _DATE.finditer(text):
        context = normalize(_line(text, m.start()))
        if not any(x in context for x in (
            "data", "inicio", "termino", "inscri", "edital", "validade", "prazo",
        )):
            continue
        val = _date_value(m.group())
        if val is not None:
            add(m, FactKind.DATE, val, "iso_date")
    return tuple(sorted(facts, key=lambda fact: (fact.start, fact.end, fact.kind)))
