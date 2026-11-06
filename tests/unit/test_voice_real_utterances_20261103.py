"""Regressões de intenções reais na captura do Orelhão em 03/11."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from orelhao.config import load_config
from orelhao.hardware.voice_intents import VoiceIntentRouter
from orelhao.hardware.voice_prompts import PROMPTS
from orelhao.services.knowledge.local_clock import answer_local_clock

FIXED = datetime(2026, 11, 3, 15, 12, tzinfo=UTC)


def test_menu_cursos_aceita_fala_natural_na_sequencia() -> None:
    router = VoiceIntentRouter()
    assert router.route("Quais os custos do Senac?").prompt == "courses_or_prices"
    choice = router.route("Vamos saber sobre os cursos.")
    assert choice is not None and choice.prompt == "courses_overview"
    assert router.awaiting_course_area


@pytest.mark.parametrize("phrase", [
    "Vamos falar sobre os cursos.",
    "Vamos conversar sobre cursos.",
    "Quero saber os cursos.",
    "Eu quero conhecer os cursos.",
    "Os cursos do Senac.",
])
def test_selecoes_gerais_de_cursos(phrase: str) -> None:
    route = VoiceIntentRouter().route(phrase)
    assert route is not None and route.prompt == "courses_overview"


@pytest.mark.parametrize("phrase", [
    "Ei, que dia é hoje?",
    "E que dia é hoje?",
    "Oi, Lumi, que horas são?",
    "Olá! Qual a data atual?",
])
def test_relogio_com_vocativos(phrase: str) -> None:
    answer = answer_local_clock(phrase, now=FIXED)
    assert answer is not None
    assert answer.kind in {"date", "time"}
    assert ("3 de novembro de 2026" in answer.text
            or "12 horas e 12 minutos" in answer.text)


@pytest.mark.parametrize("phrase", [
    "Ei, que dia o Senac abre?",
    "Oi, Lumi, há vagas hoje?",
    "Que dia é hoje e há matrículas abertas?",
    "Que horas começa o curso de Enfermagem?",
])
def test_consultas_institucionais_nao_herdam_whitelist_de_relogio(
    phrase: str,
) -> None:
    assert answer_local_clock(phrase, now=FIXED) is None


def test_pergunta_configuracao_explicita_e_frase_ambigua() -> None:
    router = VoiceIntentRouter(runtime_summary="Configuração verificada do servidor")
    assert router.route("E qual é a sua configuração?").text == (
        "Configuração verificada do servidor"
    )
    uncertain = router.route("É igual a sua configuração.")
    assert uncertain is not None and uncertain.prompt == "clarify_configuration"


def test_fragmento_ininteligivel_pede_repeticao_sem_rag() -> None:
    router = VoiceIntentRouter()
    unclear = router.route("Sois-nec.")
    assert unclear is not None and unclear.prompt == "clarify_request"
    assert router.route("Qual é a carga horária do Excel?") is None


def test_greeting_curta_sem_instrucao_extra() -> None:
    assert PROMPTS["greeting"] == "Olá! Eu sou o Lumi. Como posso ajudar?"


def test_glossario_stt_servidor_nao_contem_metalinguagem(server_profile_path: Path) -> None:
    config = load_config(server_profile_path)
    assert config.stt.initial_prompt is not None
    assert "Transcrição" not in config.stt.initial_prompt
    assert "Senac" in config.stt.initial_prompt
    assert config.audio.pipewire_warmup_seconds == 2.6
