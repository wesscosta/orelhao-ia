from __future__ import annotations

import argparse
import os
from pathlib import Path

from orelhao.config import load_config
from orelhao.core.conversation.session import Session
from orelhao.core.conversation.state_machine import ConversationStateMachine, State
from orelhao.infrastructure.telemetry.metrics import Metrics
from orelhao.interfaces.voice.audio import PCM16Audio
from orelhao.interfaces.voice.capture import (
    AudioCapture,
    MockAudioCapture,
    build_audio_capture,
)
from orelhao.interfaces.voice.devices import inspect_device
from orelhao.interfaces.voice.playback import MockAudioPlayback, SoundDeviceAudioPlayback
from orelhao.services.llm.service import MockLLMService
from orelhao.services.knowledge import Document, KnowledgeService
from orelhao.services.rag.retriever import MockRetriever
from orelhao.services.stt.service import FasterWhisperSTTService, MockSTTService
from orelhao.services.tts.provision import provision_piper_voice
from orelhao.services.tts.service import MockTTSService, PiperTTSService
from orelhao.runtime_paths import resolve_project_path


def _config():
    path = os.getenv("ORELHAO_CONFIG", "config/development.yaml")
    return load_config(resolve_project_path(path))


def run_mock_pipeline() -> None:
    config = _config()
    machine = ConversationStateMachine()
    session = Session()
    metrics = Metrics(sessions_started=1)

    capture = MockAudioCapture(config.audio.sample_rate)
    playback = MockAudioPlayback()
    stt = MockSTTService()
    retriever = MockRetriever()
    llm = MockLLMService()
    tts = MockTTSService()

    print(f"{config.name} [{config.environment}] — sessão {session.id}")
    machine.transition(State.OFF_HOOK)
    machine.transition(State.LISTENING)
    audio = capture.capture()

    machine.transition(State.TRANSCRIBING)
    transcription = stt.transcribe(audio)
    query = transcription.text
    print(f"Usuário: {query}")

    machine.transition(State.RETRIEVING)
    context = retriever.search(query)
    machine.transition(State.GENERATING)
    answer = llm.generate(query, context)
    print(f"Assistente: {answer}")

    machine.transition(State.SPEAKING)
    playback.play(tts.synthesize(answer))
    session.register_turn()
    metrics.turns_completed += 1
    machine.transition(State.ON_HOOK)
    print(f"Sessão finalizada. Estado={machine.state}; turnos={session.turns}")


def audio_loopback() -> None:
    config = _config()
    capture = build_audio_capture(config.audio)
    playback = SoundDeviceAudioPlayback(config.audio)
    print("Calibrando o ambiente; aguarde o aviso para falar...")
    audio = capture.capture()
    _print_capture_diagnostics(capture)
    if not audio.data:
        print("Nenhuma fala detectada.")
        return
    print(f"Capturado: {audio.duration_seconds:.2f}s. Reproduzindo...")
    playback.play(audio)


def stt_test() -> None:
    config = _config()
    capture = build_audio_capture(config.audio)
    stt = FasterWhisperSTTService(config.stt)

    print(
        f"STT local: model={config.stt.model} device={config.stt.device} "
        f"compute={config.stt.compute_type}"
    )
    print("Calibrando o ambiente; aguarde o aviso para falar...")
    audio = capture.capture()
    _print_capture_diagnostics(capture)
    if not audio.data:
        print("Nenhuma fala detectada.")
        return

    print(f"Áudio capturado: {audio.duration_seconds:.2f}s")
    print("Transcrevendo...")
    result = stt.transcribe(audio)
    print(f"Texto: {result.text or '[vazio]'}")
    print(
        "Métricas: "
        f"STT={result.elapsed_seconds:.3f}s | "
        f"áudio={result.audio_seconds:.3f}s | "
        f"RTF={result.real_time_factor:.3f} | "
        f"idioma={result.language} | "
        f"confiança={_fmt_probability(result.language_probability)} | "
        f"segmentos={result.segments} | "
        f"cpu_fallback={stt.used_cpu_fallback}"
    )


def stt_file(path: str) -> None:
    config = _config()
    payload = Path(path).read_bytes()
    audio = PCM16Audio.from_wav_bytes(payload)
    stt = FasterWhisperSTTService(config.stt)
    result = stt.transcribe(audio)
    print(result.text)
    print(
        f"[STT {result.elapsed_seconds:.3f}s | áudio {result.audio_seconds:.3f}s | "
        f"RTF {result.real_time_factor:.3f}]"
    )



def tts_test(text: str) -> None:
    config = _config()
    tts = PiperTTSService(config.tts)
    playback = SoundDeviceAudioPlayback(config.audio)
    print(f"TTS local: backend={config.tts.backend} model={config.tts.model}")
    result = tts.synthesize_result(text)
    print(
        f"TTS={result.elapsed_seconds:.3f}s | áudio={result.audio_seconds:.3f}s | "
        f"RTF={result.real_time_factor:.3f}"
    )
    playback.play(result.audio)


def voice_test() -> None:
    config = _config()
    capture = build_audio_capture(config.audio)
    stt = FasterWhisperSTTService(config.stt)
    tts = PiperTTSService(config.tts)
    playback = SoundDeviceAudioPlayback(config.audio)
    print("Calibrando o ambiente; aguarde o aviso para falar...")
    audio = capture.capture()
    _print_capture_diagnostics(capture)
    if not audio.data:
        print("Nenhuma fala detectada.")
        return
    transcription = stt.transcribe(audio)
    print(f"Texto: {transcription.text or '[vazio]'}")
    if not transcription.text.strip():
        return
    result = tts.synthesize_result(transcription.text)
    print(
        f"STT={transcription.elapsed_seconds:.3f}s | TTS={result.elapsed_seconds:.3f}s | "
        f"TTS_RTF={result.real_time_factor:.3f}"
    )
    playback.play(result.audio)


def rag_test(query: str) -> None:
    """Smoke test determinístico da fundação RAG sem embeddings/LLM real."""
    knowledge = KnowledgeService()
    knowledge.ingest(
        [
            Document(
                id="getting-started",
                title="Atendimento",
                source="demo/atendimento.md",
                text=(
                    "O terminal pode operar offline quando modelos e base de conhecimento "
                    "estão provisionados localmente. A rede é auxiliar para atualizações, "
                    "telemetria e manutenção autorizada."
                ),
            ),
            Document(
                id="architecture",
                title="Arquitetura",
                source="demo/arquitetura.md",
                text=(
                    "A base de conhecimento é configurável por implantação. O core não deve "
                    "depender do domínio, do modelo de embeddings ou do vector store escolhido."
                ),
            ),
        ],
        chunk_size=320,
        overlap=40,
    )
    context = knowledge.retrieve(query, limit=3)
    print(f"Consulta: {query}")
    if not context.has_evidence:
        print("Nenhuma evidência encontrada na base de demonstração.")
        return
    print(context.text)


def _fmt_probability(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"



def _print_capture_diagnostics(capture: AudioCapture) -> None:
    diag = capture.last_diagnostics
    if diag is None:
        return
    print(
        "Áudio: "
        f"hardware={diag.hardware_rate}Hz → pipeline={diag.pipeline_rate}Hz | "
        f"noise={diag.noise_floor:.5f} | threshold={diag.speech_threshold:.5f} | "
        f"peak={diag.peak_rms:.5f} | "
        f"fim={diag.stop_reason} | falsos_inicios={diag.false_starts} | "
        f"overflows={diag.overflow_count}"
    )


def audio_diagnose() -> None:
    config = _config()
    try:
        import sounddevice as sd
    except ImportError as exc:
        raise SystemExit("Instale o suporte de áudio: pip install -e '.[audio]'") from exc

    for kind, device in (("input", config.audio.input_device), ("output", config.audio.output_device)):
        status = inspect_device(sd, device, kind, config.audio.channels)
        if status.available:
            print(
                f"{kind.upper()}: OK | selector={device!r} | index={status.resolved_index} | {status.name} | "
                f"native={status.native_sample_rate}Hz | channels={status.channels}"
            )
        else:
            print(f"{kind.upper()}: ERRO | device={device!r} | {status.error}")


def provision_tts() -> None:
    config = _config()
    voice = provision_piper_voice(config.tts)
    print(f"Voz Piper provisionada: {voice.model}")
    print(f"Config: {voice.config}")
    print(f"Licença/model card: {voice.model_card}")


def list_audio_devices() -> None:
    try:
        import sounddevice as sd
    except ImportError as exc:
        raise SystemExit("Instale o suporte de áudio: pip install -e '.[audio]'") from exc
    devices = list(sd.query_devices())
    for index, info in enumerate(devices):
        inputs = int(info["max_input_channels"])
        outputs = int(info["max_output_channels"])
        roles = []
        if inputs > 0:
            roles.append(f"IN:{inputs}")
        if outputs > 0:
            roles.append(f"OUT:{outputs}")
        if not roles:
            continue
        print(f"{index:>2} | {' '.join(roles):<12} | {info['name']}")
    print("\nPara maior estabilidade, prefira configurar input_device/output_device pelo nome.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Orelhão IA")
    parser.add_argument("--audio-loopback", action="store_true", help="testa captura + VAD + playback")
    parser.add_argument("--list-audio-devices", action="store_true", help="lista interfaces de áudio")
    parser.add_argument("--audio-diagnose", action="store_true", help="valida input/output configurados")
    parser.add_argument("--stt-test", action="store_true", help="captura fala e transcreve localmente")
    parser.add_argument("--stt-file", metavar="WAV", help="transcreve um WAV PCM16 mono 16 kHz")
    parser.add_argument("--tts-test", metavar="TEXT", help="sintetiza texto localmente e reproduz")
    parser.add_argument("--tts-provision", action="store_true", help="baixa/provisiona a voz PT-BR configurada")
    parser.add_argument("--voice-test", action="store_true", help="captura → STT → TTS → playback")
    parser.add_argument("--rag-test", metavar="QUERY", help="testa ingestão + recuperação local determinística")
    args = parser.parse_args()

    if args.list_audio_devices:
        list_audio_devices()
    elif args.audio_diagnose:
        audio_diagnose()
    elif args.audio_loopback:
        audio_loopback()
    elif args.stt_test:
        stt_test()
    elif args.stt_file:
        stt_file(args.stt_file)
    elif args.tts_provision:
        provision_tts()
    elif args.tts_test:
        tts_test(args.tts_test)
    elif args.voice_test:
        voice_test()
    elif args.rag_test:
        rag_test(args.rag_test)
    else:
        run_mock_pipeline()


if __name__ == "__main__":
    main()
