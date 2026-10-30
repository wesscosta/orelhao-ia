from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from orelhao.services.knowledge.local_clock import answer_local_clock

FIXED = datetime(2026, 10, 30, 15, 7, tzinfo=UTC)


@pytest.mark.parametrize("question,kind", [
    ("Que dia é hoje?", "date"),
    ("Lumi, que dia é hoje?", "date"),
    ("Hoje é que dia?", "date"),
    ("Qual é a data atual?", "date"),
    ("Qual o dia da semana de hoje?", "date"),
    ("Em que dia estamos?", "date"),
    ("Que horas são agora?", "time"),
    ("Que hora é agora?", "time"),
    ("Qual é o horário atual?", "time"),
    ("Me diga as horas!", "time"),
    ("Que dia é hoje? Que horas são agora?", "date_time"),
    ("Que dia é hoje e que horas são agora?", "date_time"),
])
def test_whitelisted_clock_intents(question: str, kind: str) -> None:
    answer = answer_local_clock(question, now=FIXED)
    assert answer is not None
    assert answer.kind == kind
    assert answer.timezone == "America/Fortaleza"
    assert answer.timestamp == "2026-10-30T12:07:00-03:00"
    assert "sexta-feira, 30 de outubro de 2026" in answer.text if "date" in kind else True
    assert "12 horas e 7 minutos" in answer.text if "time" in kind else True


@pytest.mark.parametrize("question", [
    "Há vagas disponíveis hoje?",
    "Qual o horário de atendimento do Senac?",
    "Qual é o horário de atendimento hoje?",
    "O Senac abre agora?",
    "Qual a data da matrícula?",
    "O Senac vai abrir hoje?",
    "Que dia é hoje e há vagas?",
    "Quantas vagas há hoje?",
    "Que horas são as aulas de hoje?",
    "Qual o prazo de resposta da Ouvidoria hoje?",
    "Qual o curso de hoje?",
    "Você sabe qual é a data do próximo edital?",
])
def test_institutional_temporal_questions_do_not_bypass_rag(question: str) -> None:
    assert answer_local_clock(question, now=FIXED) is None


def test_crosses_day_boundary_using_configured_timezone() -> None:
    instant = datetime(2026, 10, 31, 1, 5, tzinfo=UTC)
    answer = answer_local_clock("Que dia é hoje?", now=instant)
    assert answer is not None
    assert "sexta-feira, 30 de outubro de 2026" in answer.text
    assert answer.timestamp == "2026-10-30T22:05:00-03:00"


def test_clock_uses_selected_timezone() -> None:
    answer = answer_local_clock(
        "Que horas são agora?", timezone="America/Sao_Paulo", now=FIXED
    )
    assert answer is not None
    assert answer.timezone == ZoneInfo("America/Sao_Paulo").key
    assert "no horário de Sao Paulo" in answer.text



def test_minutes_zero_and_one_have_natural_ptbr_forms() -> None:
    base = datetime(2026, 10, 30, 4, 0, tzinfo=UTC)
    one = answer_local_clock("Que horas são agora?", now=base)
    assert one is not None and "Agora é 1 hora em ponto" in one.text
    other = answer_local_clock(
        "Que horas são agora?", now=base.replace(minute=1)
    )
    assert other is not None and "Agora é 1 hora e 1 minuto" in other.text
