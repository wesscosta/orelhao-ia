"""Regressões do fluxo de cursos por área, tema e cidade no monofone."""
from pathlib import Path

import pytest

from orelhao.hardware.voice_intents import VoiceIntentRouter
from orelhao.hardware.voice_prompts import PROMPTS


def test_fluxo_real_informatica_programacao_cidade() -> None:
    r = VoiceIntentRouter()
    assert r.route("Quais os cursos no Senac?").prompt == "courses_overview"
    assert r.route("Área de Informática.").prompt == "technology_area"
    assert r.awaiting_technology_choice
    answer = r.route("Programação.")
    assert answer is not None and answer.prompt == "programming_area"
    assert r.awaiting_programming_city
    location = r.route("Em Teresina.")
    assert location is not None and location.prompt == "programming_teresina"
    assert not r.awaiting_programming_city
    assert "2026" in PROMPTS["programming_teresina"]
    assert "Zona Leste" in PROMPTS["programming_teresina"]
    assert "40 horas" in PROMPTS["programming_teresina"]


def test_programacao_repetida_continua_no_assunto_sem_falso_erro() -> None:
    r = VoiceIntentRouter()
    r.route("Quais os cursos do Senac?")
    r.route("Área de Informática")
    assert r.route("Programação").prompt == "programming_area"
    again = r.route("Programação")
    assert again is not None and again.prompt == "programming_area"


@pytest.mark.parametrize("query", (
    "Programação",
    "Área de programação",
    "Cursos na área de programação",
    "Quero saber sobre cursos de programação",
    "Quero cursos de programação",
    "Cursos de programação no Senac",
    "O Senac tem cursos de programação?",
))
def test_pedidos_gerais_programacao_aceitos_sem_rag(query: str) -> None:
    result = VoiceIntentRouter().route(query)
    assert result is not None and result.prompt == "programming_area"


def test_piripiri_programacao_e_atualidade() -> None:
    r = VoiceIntentRouter()
    r.route("Quero cursos de programação")
    reply = r.route("Piripiri")
    assert reply is not None and reply.prompt == "programming_piripiri"
    assert "Técnico em Desenvolvimento de Sistemas" in PROMPTS[reply.prompt]
    assert "1200 horas" in PROMPTS[reply.prompt]
    assert "2026" in PROMPTS[reply.prompt]


def test_cidade_sem_exemplo_na_base_nao_nega_oferta() -> None:
    r = VoiceIntentRouter()
    r.route("Programação")
    reply = r.route("Parnaíba")
    assert reply is not None and reply.prompt == "programming_city_unverified"
    assert "não" in PROMPTS[reply.prompt].lower()
    assert "não há cursos" not in PROMPTS[reply.prompt].lower()


@pytest.mark.parametrize("question", [
    "Qual o preço do curso de programação?",
    "Quanto custa aprender programação?",
    "Tem vagas em programação hoje?",
    "Qual a matrícula do curso de programação?",
    "Qual a carga horária do curso de programação?",
    "Quais os requisitos para o técnico em desenvolvimento de sistemas?",
])
def test_detalhes_e_oferta_atual_continuam_no_grounding(question: str) -> None:
    r = VoiceIntentRouter()
    assert r.route(question) is None


def test_nova_pergunta_nao_e_consumida_como_cidade() -> None:
    r = VoiceIntentRouter()
    r.route("Cursos de programação")
    assert r.awaiting_programming_city
    assert r.route("Qual o preço do curso de Excel?") is None
    assert not r.awaiting_programming_city


def test_programacao_nao_inventa_vagas_abertas() -> None:
    assert "2026" in PROMPTS["programming_area"]
    assert "turma aberta" not in PROMPTS["programming_area"].lower()
    assert "2026" in PROMPTS["programming_teresina"]
    assert "2026" in PROMPTS["programming_piripiri"]


def test_referencias_historicas_comprovadas_no_corpus() -> None:
    source = Path("knowledge/sources/cursos/tecnologia-qualificacoes-2026.md")
    text = source.read_text(encoding="utf-8")
    assert "source_url:" in text and "published_at:" in text
    for term in (
        "Aprendendo Programação com Minecraft",
        "Teresina — Zona Leste",
        "Técnico em Desenvolvimento de Sistemas",
        "Piripiri",
    ):
        assert term in text

@pytest.mark.parametrize("utterance,expected", [
    ("E em Teresina?", "programming_teresina"),
    ("E Teresina?", "programming_teresina"),
    ("Na Zona Leste", "programming_teresina"),
    ("Quero em Piripiri", "programming_piripiri"),
    ("Em Picos", "programming_city_unverified"),
])
def test_followup_de_localidade_natural(
    utterance: str, expected: str,
) -> None:
    router = VoiceIntentRouter()
    router.route("Cursos de programação")
    result = router.route(utterance)
    assert result is not None and result.prompt == expected


def test_pergunta_de_vagas_em_tempo_real_nao_usa_catalogo_historico() -> None:
    router = VoiceIntentRouter()
    router.route("Cursos de programação")
    assert router.route("E em Teresina tem vagas abertas hoje?") is None
    assert not router.awaiting_programming_city
