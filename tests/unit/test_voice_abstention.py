"""Tom físico das abstenções: com humor, sem alterar o grounding do workbench."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from orelhao.hardware import voice_worker
from orelhao.hardware.voice_abstention import VoiceAbstentionPolicy
from orelhao.hardware.voice_intents import VoiceIntentRouter
from orelhao.hardware.voice_prompts import PROMPTS


def test_brincadeira_somente_na_primeira_abstencao_generica() -> None:
    policy = VoiceAbstentionPolicy()
    assert policy.choose_prompt("Onde fica o laboratório de astronomia?") == "abstention_humor"
    assert policy.choose_prompt("Qual a cor da sala de robótica?") == "abstention_followup"
    assert policy.choose_prompt("Outro assunto sem resposta?") == "abstention_followup"
    assert policy.refusals == 3


def test_nova_ligacao_renova_personalidade() -> None:
    old = VoiceAbstentionPolicy()
    old.choose_prompt("Uma pergunta sem evidências?")
    assert VoiceAbstentionPolicy().choose_prompt("Outra pergunta?") == "abstention_humor"


@pytest.mark.parametrize(("question", "expected"), [
    ("Tem vagas no curso de Excel?", "abstention_admissions"),
    ("Quanto custa o curso de programação?", "abstention_admissions"),
    ("Quando abre a matrícula?", "abstention_admissions"),
    ("Qual o valor do curso?", "abstention_admissions"),
    ("Minha frequência está correta?", "abstention_pedagogy"),
    ("Como funciona a avaliação do aluno?", "abstention_pedagogy"),
    ("Qual o endereço da supervisão?", "abstention_humor"),
])
def test_encaminhamento_sem_inventar_enderecos(
    question: str, expected: str,
) -> None:
    assert VoiceAbstentionPolicy().choose_prompt(question) == expected


def test_incompreensao_do_whisper_nao_e_abstencao_factual() -> None:
    result = VoiceIntentRouter().route("Sois-nec.")
    assert result is not None and result.prompt == "clarify_request"


def test_roteamento_das_falas_da_captura() -> None:
    router = VoiceIntentRouter()
    assert router.route("Cursos disponíveis. Alô.").prompt == "courses_current"
    assert router.route("Informações vocês tem.").prompt == "lumi_capabilities"
    assert router.route("Qual Senac mais próximo?").prompt == "ask_location"
    assert router.route("Sua estereza na Piauí.").prompt == "clarify_location"
    assert router.awaiting_location
    assert router.route("Estou em Teresina.").text is not None


def test_apos_duas_localidades_imprecisas_orienta_atendimento() -> None:
    router = VoiceIntentRouter()
    router.route("Qual Senac mais próximo?")
    assert router.route("Sua estereza na Piauí").prompt == "clarify_location"
    assert router.route("Sua estereza na Piauí").prompt == "location_referral"
    assert not router.awaiting_location


def test_worker_fala_fallback_preserva_justificativa_do_rag(monkeypatch) -> None:
    played: list[str] = []
    events: list[tuple[str, dict]] = []
    asked: list[str] = []
    syntheses: list[str] = []
    phrases = iter((
        "Qual a cor da sala de robótica?",
        "Qual a cor da sala de robótica?",
        "Finaliza.",
    ))

    class Capture:
        last_diagnostics = None

        def capture(self):
            return SimpleNamespace(data=b"voice")

    class STT:
        def __init__(self, _cfg):
            pass

        def transcribe(self, _audio):
            return SimpleNamespace(text=next(phrases))

    class TTS:
        def __init__(self, _cfg):
            pass

        def synthesize(self, text):
            syntheses.append(text)
            return text

    class Playback:
        def __init__(self, _cfg):
            pass

        def play(self, audio):
            played.append(audio)

    raw_answer = "Não encontrei evidências suficientes na base."
    reason = SimpleNamespace(value="nli_uncertain")

    class Workbench:
        def observe(self, question, *, mode):
            asked.append(question)
            assert mode == "enforce"
            return SimpleNamespace(
                presented_answer=raw_answer,
                answer_origin="rag",
                grounding_v3=SimpleNamespace(should_abstain=True, reason=reason),
            )

    monkeypatch.setattr(voice_worker, "publish", lambda name, **data: events.append((name, data)))
    monkeypatch.setattr(voice_worker, "ensure_audio_ready", lambda: True)
    monkeypatch.setattr(
        voice_worker, "load_config",
        lambda _path: SimpleNamespace(audio=None, stt=None, tts=None, llm=None),
    )
    monkeypatch.setattr(voice_worker, "resolve_project_path", lambda p: p)
    monkeypatch.setattr(voice_worker, "build_audio_capture", lambda _cfg: Capture())
    monkeypatch.setattr(voice_worker, "FasterWhisperSTTService", STT)
    monkeypatch.setattr(voice_worker, "PiperTTSService", TTS)
    monkeypatch.setattr(voice_worker, "SoundDeviceAudioPlayback", Playback)
    monkeypatch.setattr(voice_worker, "LocalOpenAICompatibleLLMService", lambda _cfg: object())
    monkeypatch.setattr(voice_worker, "LocalLLMAnswerGenerator", lambda _llm: object())
    monkeypatch.setattr(
        voice_worker, "default_knowledge_paths",
        lambda: SimpleNamespace(index="/tmp"),
    )
    monkeypatch.setattr(
        voice_worker, "build_default_observation_workbench",
        lambda *_args, **_kwargs: Workbench(),
    )

    voice_worker.run_call(max_seconds=100, max_turns=4)
    assert len(asked) == 2
    assert played == [
        PROMPTS["greeting"],
        PROMPTS["abstention_humor"],
        PROMPTS["abstention_followup"],
        PROMPTS["closing"],
    ]
    # O dublê Piper não possui cache; importa garantir que a recusa bruta não seja falada.
    assert syntheses == played
    assert raw_answer not in syntheses
    refusals = [
        item for name, item in events
        if name == "voice.response" and item.get("status") == "abstencao"
    ]
    assert len(refusals) == 2
    assert [item["text"] for item in refusals] == [
        PROMPTS["abstention_humor"], PROMPTS["abstention_followup"],
    ]
    assert all(item["reason"] == "nli_uncertain" for item in refusals)
    assert all(item["route"] == "rag" for item in refusals)


def test_audio_de_recusa_nao_afirma_ter_encontrado_evidencias() -> None:
    for name in ("abstention_humor", "abstention_followup", "abstention_admissions",
                 "abstention_pedagogy"):
        text = PROMPTS[name].lower()
        assert "não" in text
        assert "vagas abertas hoje" not in text
