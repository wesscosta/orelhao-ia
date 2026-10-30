"""Responde a consultas estritas sobre data/hora sem consulta ao RAG/LLM."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

WEEKDAYS = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo")
MONTHS = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro")
DATE_PATTERNS = (
    r"que dia (?:e )?hoje", r"hoje e que dia",
    r"qual (?:e )?(?:a )?data (?:de hoje|atual)",
    r"qual (?:e )?(?:o )?dia (?:de hoje|da semana hoje)",
    r"em que dia estamos",
    r"qual (?:e )?(?:o )?dia da semana (?:de )?hoje",
)
TIME_PATTERNS = (
    r"que horas sao(?: agora| hoje)?", r"que hora e(?: agora)?",
    r"qual (?:e )?(?:a )?hora (?:agora|atual)",
    r"qual (?:e )?(?:o )?horario (?:atual|agora)",
    r"me diga (?:as )?horas",
    r"pode me dizer que horas sao(?: agora)?",
)


@dataclass(frozen=True, slots=True)
class LocalClockAnswer:
    text: str
    kind: str
    timezone: str
    timestamp: str


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return "".join(c for c in normalized if not unicodedata.combining(c))


def _kind(question: str) -> str | None:
    text = _fold(question.strip())
    text = re.sub(r"^(?:o )?lumi[,;:] *", "", text)

    def classify(part: str) -> str | None:
        part = re.sub(r"^(?:lumi|o lumi)\s+", "", part).strip()
        part = re.sub(r"\s+por favor$", "", part).strip()
        if any(re.fullmatch(p, part) for p in DATE_PATTERNS):
            return "date"
        if any(re.fullmatch(p, part) for p in TIME_PATTERNS):
            return "time"
        return None

    segments = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"[?!.;,]+", text)]
    segments = [p for p in segments if p]
    if not segments:
        return None
    seen: set[str] = set()
    for part in segments:
        direct = classify(part)
        if direct is not None:
            seen.add(direct)
            continue
        parts = re.split(r"\s+e\s+(?=(?:que|qual|em que|me diga|pode me dizer)\b)", part)
        if len(parts) < 2:
            return None
        for sub in parts:
            kind = classify(sub)
            if kind is None:
                return None
            seen.add(kind)
    return "date_time" if len(seen) == 2 else next(iter(seen))


def answer_local_clock(
    question: str, *, timezone: str = "America/Fortaleza",
    now: datetime | None = None,
) -> LocalClockAnswer | None:
    kind = _kind(question)
    if kind is None:
        return None
    zone = ZoneInfo(timezone)
    moment = now.astimezone(zone) if now is not None else datetime.now(zone)
    date_part = (
        f"Hoje é {WEEKDAYS[moment.weekday()]}, {moment.day} "
        f"de {MONTHS[moment.month - 1]} de {moment.year}."
    )
    city = timezone.rsplit("/", 1)[-1].replace("_", " ")
    hour_label = (
        f"{moment.hour} hora" if moment.hour == 1 else f"{moment.hour} horas"
    )
    minute_label = (
        "em ponto" if moment.minute == 0
        else f"e {moment.minute} minuto" if moment.minute == 1
        else f"e {moment.minute} minutos"
    )
    verb = "é" if moment.hour == 1 else "são"
    time_part = f"Agora {verb} {hour_label} {minute_label}, no horário de {city}."
    chunks = []
    if kind in {"date", "date_time"}:
        chunks.append(date_part)
    if kind in {"time", "date_time"}:
        chunks.append(time_part)
    return LocalClockAnswer(
        " ".join(chunks), kind, timezone, moment.isoformat()
    )
