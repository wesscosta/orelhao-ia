"""A full experimental voice call. The serial supervisor owns termination."""
from __future__ import annotations

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

from orelhao.config import load_config
from orelhao.hardware.conversation_context import ContextResolution, ConversationContext
from orelhao.hardware.hook_runtime import ensure_audio_ready
from orelhao.hardware.idle_policy import CallIdlePolicy
from orelhao.hardware.live_monitor import publish, voice_observation_log_path
from orelhao.hardware.turn_taking import TurnTakingPlayback
from orelhao.hardware.voice_abstention import VoiceAbstentionPolicy
from orelhao.hardware.voice_intents import (
    VoiceIntentRouter,
    looks_like_stt_hallucination,
    runtime_description,
)
from orelhao.hardware.voice_prompts import PROMPTS, VoicePromptCache
from orelhao.interfaces.voice.capture import build_audio_capture
from orelhao.interfaces.voice.playback import SoundDeviceAudioPlayback
from orelhao.runtime_paths import resolve_project_path
from orelhao.services.knowledge.local_clock import answer_local_clock
from orelhao.services.knowledge.observation import (
    LocalLLMAnswerGenerator,
    build_default_observation_workbench,
)
from orelhao.services.knowledge.paths import default_knowledge_paths
from orelhao.services.llm.service import LocalOpenAICompatibleLLMService
from orelhao.services.stt.service import FasterWhisperSTTService
from orelhao.services.tts.service import PiperTTSService

LOG = logging.getLogger(__name__)


def run_call(*, max_seconds: int = 180, max_turns: int = 12) -> None:
    """Use only the V3 presented answer, never a raw unverified LLM answer."""
    if max_seconds < 1 or max_turns < 1:
        raise ValueError("limites da sessão devem ser positivos")
    path = os.environ.get("ORELHAO_CONFIG", "config/development.yaml")
    config = load_config(resolve_project_path(path))
    capture = build_audio_capture(config.audio)
    stt = FasterWhisperSTTService(config.stt)
    tts = PiperTTSService(config.tts)
    prompts = VoicePromptCache(tts)
    intents = VoiceIntentRouter(runtime_summary=runtime_description(config))
    context = ConversationContext()
    playback = TurnTakingPlayback(SoundDeviceAudioPlayback(config.audio))
    if not ensure_audio_ready():
        raise RuntimeError("Rota P3 indisponível antes da saudação")
    deadline = time.monotonic() + max_seconds
    LOG.info("atendimento_iniciado")
    # Pré-aquecer o PipeWire durante a saudação elimina o transiente da
    # primeira abertura; não cria segunda inferência nem gravação persistente.
    with ThreadPoolExecutor(max_workers=2) as startup:
        prime = getattr(capture, "prime", None)
        warmup_future = startup.submit(prime) if callable(prime) else None
        workbench_future = startup.submit(
            build_default_observation_workbench,
            default_knowledge_paths().index,
            answer_generator=LocalLLMAnswerGenerator(LocalOpenAICompatibleLLMService(config.llm)),
            log_path=voice_observation_log_path(),
        )
        greeting_start = time.monotonic()
        LOG.info("saudacao_iniciada")
        publish("voice.greeting", status="reproduzindo", text=PROMPTS["greeting"])
        playback.play(prompts.audio("greeting"))
        LOG.info(
            "saudacao_concluida duracao_ms=%.0f",
            (time.monotonic() - greeting_start) * 1000,
        )
        workbench = workbench_future.result()
        if warmup_future is not None:
            try:
                warmup_future.result()
            except Exception:
                LOG.exception("falha_aquecimento_pipewire; continuar com captura normal")
    publish("voice.playback", status="saudacao_concluida", metrics={"play_ms": (time.monotonic() - greeting_start) * 1000})
    idle = CallIdlePolicy()
    abstentions = VoiceAbstentionPolicy()
    valid_turns = 0
    closed_by_voice = False
    closed_by_inactivity = False
    # Capturas sem fala ou com transcrição rejeitada não consomem o orçamento de perguntas.
    # O limite de tentativas e o deadline impedem sessões indefinidas.
    for turn in range(1, max_turns * 3 + 1):
        if time.monotonic() >= deadline or valid_turns >= max_turns:
            break
        if not ensure_audio_ready():
            raise RuntimeError("Rota P3 indisponível antes da captura")
        # Nao abrir o microfone antes do fim do TTS e do intervalo antieco.
        playback.wait_before_capture()
        if time.monotonic() >= deadline:
            break
        LOG.info("escuta_iniciada turno=%d", turn)
        publish(
            "voice.listening", turn=turn,
            status="aguardando_retorno" if idle.paused else "escutando",
        )
        capture_start = time.monotonic()
        audio = capture.capture()
        capture_ms = (time.monotonic() - capture_start) * 1000
        diagnostics = capture.last_diagnostics
        if diagnostics is not None:
            LOG.info(
                "audio_capture turno=%d motivo=%s detectou_fala=%s "
                "noise_floor=%.5f limiar=%.5f pico_rms=%.5f overflows=%d",
                turn,
                diagnostics.stop_reason,
                diagnostics.speech_detected,
                diagnostics.noise_floor,
                diagnostics.speech_threshold,
                diagnostics.peak_rms,
                diagnostics.overflow_count,
            )
        if diagnostics is not None:
            publish("voice.capture", turn=turn, status=diagnostics.stop_reason,
                    metrics={"capture_ms": capture_ms,
                             "peak_rms": diagnostics.peak_rms,
                             "noise_floor": diagnostics.noise_floor,
                             "threshold": diagnostics.speech_threshold})
        else:
            publish("voice.capture", turn=turn, status="concluida",
                    metrics={"capture_ms": capture_ms})
        if time.monotonic() >= deadline:
            break
        if not audio.data:
            LOG.info("escuta_sem_fala turno=%d", turn)
            publish("voice.transcription_invalid", turn=turn, status="sem_fala")
            decision = idle.on_missing_speech()
            if decision == "close":
                LOG.info("atendimento_encerrado_por_inatividade modo=%s", "pausa" if idle.paused else "normal")
                publish("voice.idle_timeout", turn=turn, status="encerrando")
                closed_by_inactivity = True
                break
            if decision == "prompt" and time.monotonic() < deadline:
                if not ensure_audio_ready():
                    raise RuntimeError("Rota P3 indisponível antes do aviso")
                publish("voice.response", turn=turn, status="aviso", route="prompt",
                        text=PROMPTS["idle_check"])
                playback.play(prompts.audio("idle_check"))
            continue
        stt_start = time.monotonic()
        transcribed = stt.transcribe(audio)
        stt_ms = (time.monotonic() - stt_start) * 1000
        question = transcribed.text.strip()
        if not question or looks_like_stt_hallucination(question):
            LOG.info("transcricao_invalida turno=%d", turn)
            publish("voice.transcription_invalid", turn=turn, text=question,
                    status="suspeita" if question else "vazia",
                    metrics={"stt_ms": stt_ms})
            decision = idle.on_missing_speech()
            if decision == "close":
                LOG.info("atendimento_encerrado_por_inatividade modo=%s", "pausa" if idle.paused else "normal")
                publish("voice.idle_timeout", turn=turn, status="encerrando")
                closed_by_inactivity = True
                break
            if decision == "prompt" and time.monotonic() < deadline:
                if not ensure_audio_ready():
                    raise RuntimeError("Rota P3 indisponível antes do aviso de transcrição")
                publish("voice.response", turn=turn, status="aviso", route="prompt",
                        text=PROMPTS["no_transcription"])
                playback.play(prompts.audio("no_transcription"))
            continue
        LOG.info("transcricao_concluida turno=%d caracteres=%d", turn, len(question))
        publish("voice.transcription", turn=turn, text=question,
                status="reconhecida", metrics={"stt_ms": stt_ms})
        valid_turns += 1
        directed = intents.route(question)
        idle.on_phrase(requested_pause=intents.paused)
        if idle.paused:
            publish("voice.paused", turn=turn, status="aguardando_retorno")
        if directed is not None:
            LOG.info("resposta_guiada turno=%d tipo=%s", turn, directed.prompt or "location")
            if not ensure_audio_ready():
                raise RuntimeError("Rota P3 indisponível antes da resposta guiada")
            spoken_text = PROMPTS[directed.prompt] if directed.prompt else (directed.text or "")
            publish("voice.response", turn=turn, text=spoken_text,
                    route="guided", status="respondida")
            synth_start = time.monotonic()
            outgoing = (prompts.audio(directed.prompt) if directed.prompt is not None
                        else tts.synthesize(spoken_text))
            tts_ms = (time.monotonic() - synth_start) * 1000
            play_start = time.monotonic()
            playback.play(outgoing)
            context.remember(
                question, spoken_text,
                reset_topic=directed.prompt in {
                    "who_is_lumi", "lumi_capabilities", "ask_topic", "about_senac",
                },
            )
            publish("voice.playback", turn=turn, status="concluida",
                    metrics={"tts_ms": tts_ms, "play_ms": (time.monotonic() - play_start) * 1000})
            if directed.end_session:
                closed_by_voice = True
                LOG.info("atendimento_encerrado_por_voz turno=%d", turn)
                break
            continue

        is_clock = answer_local_clock(
            question, timezone=os.getenv('ORELHAO_TIMEZONE', 'America/Fortaleza'),
        ) is not None
        # Perguntas de relógio nunca herdam o tópico anterior do Senac.
        resolution = (ContextResolution(question=question) if is_clock
                      else context.resolve(question))
        if resolution.clarification is not None:
            spoken_text = PROMPTS["ask_specific_course"]
            publish("voice.response", turn=turn, text=spoken_text,
                    route="clarification", status="respondida")
            play_start = time.monotonic()
            playback.play(prompts.audio("ask_specific_course"))
            context.remember(question, spoken_text)
            publish("voice.playback", turn=turn, status="concluida",
                    metrics={"tts_ms": 0.0,
                             "play_ms": (time.monotonic() - play_start) * 1000})
            continue
        if resolution.used_context:
            publish("voice.context", turn=turn,
                    text=resolution.effective_question,
                    reason=resolution.reason or "continuation")
        # A pesquisa roda enquanto uma mensagem curta de espera pode ser reproduzida.
        # Perguntas rápidas não recebem esse aviso adicional.
        publish("voice.processing", turn=turn, status="consultando_base")
        with ThreadPoolExecutor(max_workers=1) as executor:
            started = time.monotonic()
            future = executor.submit(workbench.observe, resolution.effective_question, mode="enforce")
            try:
                observation = future.result(timeout=0.65)
            except FutureTimeout:
                if not ensure_audio_ready():
                    raise RuntimeError("Rota P3 indisponível antes do aviso de espera")
                publish("voice.waiting", turn=turn, text=PROMPTS["waiting"],
                        status="aguardando")
                playback.play(prompts.audio("waiting"))
                observation = future.result()
            LOG.info(
                "grounding_concluido turno=%d origem=%s duracao_ms=%.0f",
                turn, observation.answer_origin, (time.monotonic() - started) * 1000,
            )
        if time.monotonic() >= deadline:
            break
        grounding = getattr(observation, "grounding_v3", None)
        denied = bool(getattr(grounding, "should_abstain", False))
        reason = getattr(grounding, "reason", None)
        # Personalidade apenas na apresentação da abstenção física.
        # O resultado da bancada, as evidências e a razão V3 permanecem intocados.
        fallback_prompt = abstentions.choose_prompt(question) if denied else None
        spoken_text = (
            PROMPTS[fallback_prompt] if fallback_prompt is not None
            else observation.presented_answer
        )
        context.remember(question, spoken_text, reset_topic=is_clock)
        publish("voice.response", turn=turn, text=spoken_text,
                route=str(observation.answer_origin),
                status="abstencao" if denied else "respondida",
                reason=str(getattr(reason, "value", reason) or ""),
                metrics={"rag_ms": (time.monotonic() - started) * 1000})
        synth_start = time.monotonic()
        outgoing = (
            prompts.audio(fallback_prompt) if fallback_prompt is not None
            else tts.synthesize(spoken_text)
        )
        tts_ms = (time.monotonic() - synth_start) * 1000
        play_start = time.monotonic()
        playback.play(outgoing)
        publish("voice.playback", turn=turn, status="concluida",
                metrics={"tts_ms": tts_ms, "play_ms": (time.monotonic() - play_start) * 1000})
    LOG.info("atendimento_terminado")
    if not closed_by_voice and ensure_audio_ready():
        closing = "closing_inactivity" if closed_by_inactivity else "closing"
        publish("voice.playback", text=PROMPTS[closing], status="despedida")
        playback.play(prompts.audio(closing))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        run_call()
    except Exception as exc:
        publish("voice.error", status="erro", reason=type(exc).__name__)
        LOG.exception("atendimento_falhou")
        raise


if __name__ == "__main__":
    main()
