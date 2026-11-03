"""Regressões para respostas guiadas de voz e contexto curto da localização."""
from orelhao.hardware.voice_intents import VoiceIntentRouter
from orelhao.hardware.voice_prompts import PROMPTS


def test_cursos_listados_sem_inventar_vagas() -> None:
    router = VoiceIntentRouter()
    answer = router.route("Quais os cursos do Senac?")
    assert answer is not None and answer.prompt == "courses_overview"
    assert "vagas abertas" not in PROMPTS[answer.prompt]
    assert router.route("Qual a carga horária do curso de Excel?") is None


def test_custos_podem_ser_erro_de_transcricao() -> None:
    router = VoiceIntentRouter()
    answer = router.route("É quais os custos do Senac?")
    assert answer is not None and answer.prompt == "courses_or_prices"


def test_senac_mais_proximo_precisa_de_localizacao() -> None:
    router = VoiceIntentRouter()
    question = router.route("Qual o Senac mais próximo?")
    assert question is not None and question.prompt == "ask_location"
    assert router.awaiting_location

    followup = router.route("Estou na Zona Sul de Teresina")
    assert followup is not None and followup.text is not None
    assert "Parque Piauí" in followup.text
    assert "Não posso garantir" in followup.text
    assert not router.awaiting_location


def test_termo_senac_nao_ativa_respostas_inadequadas() -> None:
    router = VoiceIntentRouter()
    assert router.route("Que dia é hoje?") is None
    assert router.route("O Senac tem vagas hoje?") is None
    assert router.route("Qual o endereço do Senac em Parnaíba?") is None


def test_localidade_nao_catalogada_nao_retorna_distancia_ficticia() -> None:
    router = VoiceIntentRouter()
    router.route("Qual unidade do Senac fica mais perto de mim?")
    answer = router.route("Estou no bairro desconhecido")
    assert answer is not None and answer.text is not None
    assert "Não consegui identificar" in answer.text


def test_localizacao_em_terezina_por_duas_perguntas() -> None:
    router = VoiceIntentRouter()
    router.route("Qual o Senac mais próximo?")
    city = router.route("Eu estou em Teresina")
    assert city is not None and city.text is not None
    assert "Qual é seu bairro?" in city.text
    assert router.awaiting_location
    result = router.route("No Parque Piauí")
    assert result is not None and result.text is not None
    assert "Parque Piauí" in result.text
    assert not router.awaiting_location


def test_ignorar_alucinacoes_tipicas_do_stt() -> None:
    from orelhao.hardware.voice_intents import looks_like_stt_hallucination

    assert looks_like_stt_hallucination("Transcrição e Legendas pela Amara.org")
    assert looks_like_stt_hallucination(
        "Se inscreva no canal e se inscreva no canal para ver as outras redes sociais. Que dia!"
    )
    assert not looks_like_stt_hallucination("Que dia é hoje?")
    assert not looks_like_stt_hallucination("Quais os cursos do Senac?")


def test_course_variation() -> None:
    router = VoiceIntentRouter()
    result = router.route('Quais os cursos oferecidos no Senac?')
    assert result is not None and result.prompt == 'courses_overview'


def test_course_followup_commerce() -> None:
    r = VoiceIntentRouter()
    r.route('Quais os cursos do Senac?')
    assert r.route('Área de comércio').prompt == 'commerce_area'


def test_specific_course_question_keeps_rag() -> None:
    r = VoiceIntentRouter()
    r.route('Quais os cursos do Senac?')
    assert r.route('Qual a carga horária do curso de Excel?') is None
    assert r.route('Qual o preço do curso de Excel?') is None


def test_lumi_identity_intent() -> None:
    assert VoiceIntentRouter().route('Quem é o Lumi?').prompt == 'who_is_lumi'


def test_lumi_capability_intent() -> None:
    r = VoiceIntentRouter()
    assert r.route('O que você pode me informar sobre o que você pode fazer?').prompt == 'lumi_capabilities'


def test_lumi_runtime_intent() -> None:
    r = VoiceIntentRouter(runtime_summary='Sistema local')
    assert r.route('Qual sua configuração?').text == 'Sistema local'


def test_no_automatic_location() -> None:
    r = VoiceIntentRouter()
    assert r.route('Onde estou?').prompt == 'no_location_access'
    assert r.awaiting_location
    assert r.route('Centro de Teresina').text is not None


def test_supervision_is_ambiguous() -> None:
    r = VoiceIntentRouter()
    assert r.route('Qual a supervisão mais próxima?').prompt == 'clarify_supervision'
    assert r.route('Unidade do Senac').prompt == 'ask_location'


def test_user_pause_is_not_factual_query() -> None:
    r = VoiceIntentRouter()
    assert r.route('Só um instante').prompt == 'ack_wait'
    assert r.paused
    assert r.route('Que dia é hoje?') is None
    assert not r.paused

def test_screenshot_conversation_sequence() -> None:
    router = VoiceIntentRouter()
    utterances = [
        ("Quais são os cursos do Senac hoje?", "courses_current"),
        ("Área... Comercial.", "commerce_area"),
        ("Entendi. E quais cursos, por exemplo, de gestão vocês têm?", "commerce_details"),
        ("E quem é você?", "who_is_lumi"),
        ("Eu sei.", "ack_continue"),
        ("Está bem.", "ack_continue"),
    ]
    for question, expected in utterances:
        result = router.route(question)
        assert result is not None and result.prompt == expected, question


def test_meta_questions_and_acknowledgments_do_not_query_rag() -> None:
    questions = [
        "E quem é você?", "Quem você é?", "E quem é o Lumi?",
        "Eu sei", "Está bem", "Ok", "Entendi",
    ]
    for question in questions:
        result = VoiceIntentRouter().route(question)
        assert result is not None and result.prompt is not None, question


def test_course_specific_questions_still_require_grounding() -> None:
    router = VoiceIntentRouter()
    router.route("Quais são os cursos do Senac hoje?")
    assert router.route("Qual é o valor do Excel Avançado?") is None
    assert router.route("Qual a carga horária do curso de Excel?") is None
    assert router.route("Existem vagas abertas no curso de Excel hoje?") is None
